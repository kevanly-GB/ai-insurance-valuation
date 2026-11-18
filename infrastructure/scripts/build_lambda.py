"""Assemble Python 3.12 Lambda package using Docker; run from repository root."""
from pathlib import Path
import shutil
import subprocess
import zipfile

root = Path(__file__).resolve().parents[2]
build = root / "build"
package = build / "lambda-package"
output = build / "insurance-lambda.zip"
build.mkdir(exist_ok=True)
if package.exists():
    shutil.rmtree(package)
package.mkdir()
subprocess.run([
    "docker", "run", "--rm", "--entrypoint", "/bin/bash", "-v", str(root) + ":/work",
    "public.ecr.aws/lambda/python:3.12", "-lc",
    "pip install --no-cache-dir -r /work/backend/requirements.txt -t /work/build/lambda-package"
], check=True)
shutil.copytree(root / "backend" / "app", package / "app")
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in package.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(package))
print("Built", output, "bytes:", output.stat().st_size)
print("Terraform uploads this artifact to a private S3 bucket. AWS Lambda still enforces a 250 MiB uncompressed limit.")
