"""Train a source model on clean CIFAR-10 (CPU). Usage: train.py <cnn8|resnet20> <epochs>"""
import sys, time, json, os, numpy as np, torch, torch.nn.functional as F
from common import load_cifar10, to_tensor, make_model, ROOT
torch.set_num_threads(int(os.environ.get("NT", "14"))); torch.manual_seed(0); np.random.seed(0)
name, epochs = sys.argv[1], int(sys.argv[2])
xtr, ytr = load_cifar10("train"); xte, yte = load_cifar10("test")
Xtr, Ytr = to_tensor(xtr), torch.from_numpy(ytr); Xte, Yte = to_tensor(xte), torch.from_numpy(yte)
model = make_model(name)
bs = 128; steps = epochs * (len(Xtr) // bs)
opt = torch.optim.SGD(model.parameters(), lr=0.1, momentum=0.9, weight_decay=5e-4, nesterov=True)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=0.1, total_steps=steps, pct_start=0.15)
t0 = time.time(); log = []
for ep in range(epochs):
    model.train(); perm = torch.randperm(len(Xtr))
    for k in range(len(Xtr) // bs):
        idx = perm[k * bs:(k + 1) * bs]; x = Xtr[idx]
        # augmentation: random crop with 4-pixel padding + horizontal flip
        x = F.pad(x, (4, 4, 4, 4), mode="reflect"); i, j = np.random.randint(0, 9, 2)
        x = x[:, :, i:i + 32, j:j + 32]
        if np.random.rand() < 0.5: x = x.flip(3)
        loss = F.cross_entropy(model(x), Ytr[idx])
        opt.zero_grad(); loss.backward(); opt.step(); sched.step()
    model.eval()
    with torch.no_grad():
        acc = sum((model(Xte[i:i + 1000]).argmax(1) == Yte[i:i + 1000]).sum().item() for i in range(0, 10000, 1000)) / 1e4
    log.append({"epoch": ep + 1, "loss": loss.item(), "clean_test_acc": acc, "elapsed_s": time.time() - t0})
    print(log[-1], flush=True)
os.makedirs(os.path.join(ROOT, "results", "models"), exist_ok=True)
torch.save(model.state_dict(), os.path.join(ROOT, "results", "models", f"{name}.pt"))
json.dump(log, open(os.path.join(ROOT, "results", f"train_{name}.json"), "w"), indent=1)
