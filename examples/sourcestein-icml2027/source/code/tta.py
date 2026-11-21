"""Test-time normalization statistics: source, BN-test, prior mixing, alpha-BN and SteinBN (+ ablations)."""
import torch, torch.nn as nn


class AdaptiveBN(nn.Module):
    """Wraps a trained BatchNorm2d; normalizes with statistics chosen by `rule` from the current test batch."""

    def __init__(self, bn):
        super().__init__()
        self.bn = bn
        self.rule, self.cfg = "source", {}
        self.tau2 = self.rho2 = None   # source between-sample variances of per-sample mean / second moment
        self.collect = None            # list to append per-sample statistics to (source pass)
        self.last_lam = None           # (lambda_mean, lambda_var) of the last batch, for analysis

    def per_sample(self, x):
        mu_s = self.bn.running_mean.view(1, -1)
        m = x.mean((2, 3))                                   # n x C per-sample spatial means
        u = ((x - mu_s[..., None, None]) ** 2).mean((2, 3))   # n x C per-sample second moments about mu_s
        return m, u

    @staticmethod
    def stein(y, a, noise_var, n, pooled=True):
        """Positive-part James-Stein shrinkage of the batch estimate y toward the source value a."""
        z2 = (y - a) ** 2 / (noise_var / n)
        C = y.numel()
        if pooled:
            lam = torch.clamp(1 - (C - 2) / z2.sum().clamp_min(1e-12), min=0.0)
        else:  # per-channel plug-in of the oracle weight, no pooling across channels
            lam = torch.clamp(1 - 1 / z2.clamp_min(1e-12), min=0.0)
        return a + lam * (y - a), lam

    def forward(self, x):
        bn = self.bn
        mu_s, var_s = bn.running_mean, bn.running_var
        if self.collect is not None:
            m, u = self.per_sample(x); self.collect.append((m.detach(), u.detach()))
        r, n = self.rule, x.shape[0]
        if r == "source":
            mu, var = mu_s, var_s
        else:
            m, u = self.per_sample(x)
            mu_b = m.mean(0)
            var_b = (u.mean(0) - (mu_b - mu_s) ** 2).clamp_min(1e-5)   # biased batch variance over n*H*W
            if r == "bn_test":
                mu, var = mu_b, var_b
            elif r == "prior":      # Schneider et al. (2020): prior strength N
                w = n / (n + self.cfg["N"])
                mu, var = (1 - w) * mu_s + w * mu_b, (1 - w) * var_s + w * var_b
            elif r == "alpha":      # alpha-BN (You et al., 2021): weight alpha on the SOURCE mean and std
                a = self.cfg["alpha"]
                mu = a * mu_s + (1 - a) * mu_b
                var = (a * var_s.sqrt() + (1 - a) * var_b.sqrt()) ** 2
            elif r == "stein":
                c = self.cfg
                if c.get("batch_noise", False) and n > 1:
                    tau2, rho2 = m.var(0).clamp_min(1e-8), u.var(0).clamp_min(1e-8)
                else:
                    tau2, rho2 = self.tau2, self.rho2
                pooled = c.get("pooled", True)
                mu, lam_m = self.stein(mu_b, mu_s, tau2, n, pooled)
                if c.get("var_mode", "stein") == "stein":
                    ut, lam_u = self.stein(u.mean(0), var_s, rho2, n, pooled)
                elif c["var_mode"] == "shared":
                    ut, lam_u = var_s + lam_m * (u.mean(0) - var_s), lam_m
                else:  # "source": keep source variance (mean-only adaptation)
                    ut, lam_u = var_s + (mu - mu_s) ** 2, torch.zeros(())
                var = (ut - (mu - mu_s) ** 2).clamp_min(1e-5)
                self.last_lam = (float(lam_m.mean()), float(lam_u.mean()))
            else:
                raise ValueError(r)
        xh = (x - mu[None, :, None, None]) / torch.sqrt(var[None, :, None, None] + bn.eps)
        return xh * bn.weight[None, :, None, None] + bn.bias[None, :, None, None]


def wrap(model):
    """Replace every BatchNorm2d in `model` by an AdaptiveBN; returns the list of wrappers in forward order."""
    wrappers = []
    def rec(mod):
        for name, ch in mod.named_children():
            if isinstance(ch, nn.BatchNorm2d):
                w = AdaptiveBN(ch); setattr(mod, name, w); wrappers.append(w)
            else:
                rec(ch)
    rec(model)
    return wrappers


@torch.no_grad()
def fit_source_noise(model, wrappers, x_src, bs=500):
    """One pass over clean source images: between-sample variances tau^2 (means) and rho^2 (second moments)."""
    for w in wrappers: w.rule, w.collect = "source", []
    for i in range(0, len(x_src), bs): model(x_src[i:i + bs])
    for w in wrappers:
        m = torch.cat([a for a, _ in w.collect]); u = torch.cat([b for _, b in w.collect])
        w.tau2, w.rho2 = m.var(0).clamp_min(1e-8), u.var(0).clamp_min(1e-8); w.collect = None


def set_rule(wrappers, rule, **cfg):
    for w in wrappers: w.rule, w.cfg = rule, cfg
