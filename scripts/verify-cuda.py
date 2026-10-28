import json
import sys
from pathlib import Path

import torch

if not torch.cuda.is_available():
    raise SystemExit('CUDA is not available in this isolated environment')

device = torch.device('cuda:0')
left = torch.arange(16, dtype=torch.float32, device=device).reshape(4, 4)
right = torch.eye(4, dtype=torch.float32, device=device)
result = left @ right
torch.cuda.synchronize()
if not torch.equal(result, left):
    raise SystemExit('CUDA matrix result mismatch')

print(json.dumps({
    'python': sys.executable,
    'python_version': sys.version.split()[0],
    'torch': torch.__version__,
    'torch_cuda': torch.version.cuda,
    'gpu': torch.cuda.get_device_name(0),
    'capability': list(torch.cuda.get_device_capability(0)),
    'matrix_shape': list(result.shape),
    'matrix_diagonal': result.diagonal().cpu().tolist(),
    'cuda_synchronize': 'passed',
}, indent=2))
