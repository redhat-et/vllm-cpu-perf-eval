# AMD SEV-SNP

## Create a new AWS instance

Cloud init file in `ec2/sev-vm.txt`:

```yaml
#cloud-config

packages:
- git
- mkosi
- skopeo
- uv
```

Block devices defined in `ec2/disk-mappings.json`:

```json
[
    {
        "DeviceName": "/dev/sda1",
        "Ebs": {
            "VolumeSize": 100
        }
    }
]
```

Run an EC2 instance with SEV-SNP enabled. The required option is
`--cpu-options AmdSevSnp=enabled`. The suggested AMI is a Fedora
Cloud 42 image which runs cloud-init on startup.

```bash
AMI='ami-09bf0274cea97a3ab'
INSTANCE='c6a.2xlarge'
KEY='your-key-name'
SG='your-security-group'
NAME='sev-vm'
aws ec2 run-instances \
    --image-id ${AMI} \
    --instance-type ${INSTANCE} \
    --key-name ${KEY} \
    --associate-public-ip-address \
    --user-data file://ec2/sev-vm.txt \
    --block-device-mappings file://ec2/disk-mappings.json \
    --security-group-ids ${SG} \
    --cpu-options AmdSevSnp=enabled \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]"
```

## List AMD SEV-SNP instance types

```bash
aws ec2 describe-instance-types \
    --filters Name=processor-info.supported-features,Values=amd-sev-snp \
    --query 'InstanceTypes[*].[InstanceType]' \
    --output text | sort
```

## Check SEV-SNP guest

<https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/snp-attestation.html>

```bash
curl -LO https://github.com/virtee/snpguest/releases/download/v0.10.0/snpguest
chmod +x snpguest
sudo ./snpguest ok
```
