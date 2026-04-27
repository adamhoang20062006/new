# GCP $300 Credit Optimization Guide
## YouTube Video Pipeline on Cloud Free Tier

---

## 🏆 TL;DR — Keep It Free

| Resource | Free Tier Limit | Pipeline Usage | Cost |
|---|---|---|---|
| Compute Engine e2-micro | 720 hrs/month (1 VM) | ~50-100 hrs/month | **FREE** |
| Cloud Storage | 5 GB | Video staging area | **FREE** (if <5GB) |
| Network Egress (US→) | 1 GB/month | Downloads only | **FREE** |
| YouTube Data API v3 | 10,000 units/day | ~2,050/upload | **FREE** |
| Whisper.cpp (local) | Unlimited | All transcription | **FREE** |
| Snapshots/Disk | 5 GB standard | Boot disk only | **FREE** |

**True cost of this pipeline: $0/month** if you stay within free tier limits.

---

## 📐 Instance Selection

### Always Free: e2-micro
- **2 vCPUs** (shared, burst to ~0.25 physical cores)
- **1 GB RAM**
- **30 GB standard persistent disk**
- **Region**: `us-west1`, `us-central1`, or `us-east1` only
- **Limitation**: No GPU acceleration — Whisper runs CPU-only

### For heavy workloads (use $300 credit):
| Instance | vCPU | RAM | $/hr | Good for |
|---|---|---|---|---|
| e2-small | 2 | 2GB | ~$0.017 | Whisper small.en model |
| e2-medium | 2 | 4GB | ~$0.034 | Multiple concurrent jobs |
| n2-standard-2 | 2 | 8GB | ~$0.097 | Faster FFmpeg encoding |
| n1-standard-4 + T4 GPU | 4 | 15GB | ~$0.45 | GPU-accelerated Whisper |

**$300 credit at e2-small = 17,647 hours = ~2 years runtime**
**$300 credit at n1+T4 GPU = 667 hours = ~28 days runtime**

---

## 💡 Credit-Saving Strategies

### 1. Use Preemptible/Spot VMs for batch jobs
```bash
# Create a spot VM (70-91% cheaper than regular)
gcloud compute instances create yt-pipeline-spot \
  --machine-type=n2-standard-4 \
  --zone=us-central1-a \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=50GB \
  --boot-disk-type=pd-standard
```
Cost: ~$0.03/hr vs ~$0.15/hr = **80% savings**
Risk: VM can be preempted (stopped) with 30s notice — use `--restart-on-failure`

### 2. Schedule processing windows
```bash
# Stop VM when not processing (save money during idle)
# Start: before your batch
gcloud compute instances start yt-pipeline --zone=us-central1-a

# Stop: after processing
gcloud compute instances stop yt-pipeline --zone=us-central1-a
```

### 3. Use Cloud Storage staging (avoid persistent disk costs)
```bash
# Upload raw videos to GCS free tier (5 GB)
gsutil cp local_video.mp4 gs://YOUR_BUCKET/input/

# Download to VM for processing
gsutil cp gs://YOUR_BUCKET/input/*.mp4 ~/yt-pipeline/input/

# Upload output back
gsutil cp ~/yt-pipeline/output/*.mp4 gs://YOUR_BUCKET/output/
```

### 4. e2-micro FFmpeg performance tips
```bash
# Check CPU usage during encoding
htop

# Reduce FFmpeg thread count to avoid memory OOM
ffmpeg -threads 2 -i input.mp4 ...

# Use faster preset when credit matters over quality
# preset ultrafast = 10x faster, ~15% larger file
# preset medium = balanced
# preset slow = best compression (default in our script)

# For e2-micro (1GB RAM), avoid processing >2GB files without swap
# Add swap space:
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 5. Whisper model selection for e2-micro
| Model | Size | Speed (e2-micro) | Accuracy | Recommendation |
|---|---|---|---|---|
| tiny.en | 75MB | ~5-8x realtime | Good | Quick transcription |
| base.en | 142MB | ~2-4x realtime | Better | **Default (best balance)** |
| small.en | 466MB | ~0.5-1x realtime | Great | Use with more RAM |
| medium.en | 1.5GB | May OOM | Excellent | Need e2-small+ |

### 6. Budget alerts (protect your $300)
```bash
# Set up billing alert at $50, $150, $250, $290
gcloud billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT_ID \
  --display-name="Pipeline Budget Alert - $50" \
  --budget-amount=50USD \
  --threshold-rule=percent=100

# Get your billing account ID:
gcloud billing accounts list
```

---

## 🗺️ Recommended $300 Spend Plan

### Option A: Pure free tier (recommended for most users)
- Stay on e2-micro always free
- Process videos at ~1-4x realtime (slow but free)
- **Total cost: $0/month**
- Videos per day: ~3-5 (1hr videos on base.en Whisper)

### Option B: Burst processing with credit ($300 lasts months)
- Keep e2-micro free for storage/light work
- Spin up n2-standard-4 spot for batch processing
- Process 100 videos, then stop VM
- **Cost: ~$0.06/hr spot × 10hrs = $0.60 per batch**
- $300 credit = 500 batch sessions

### Option C: GPU acceleration for large volume
- n1-standard-4 + T4 GPU (spot)
- Whisper medium model at 10-20x realtime
- FFmpeg with NVENC hardware encoding
- **Cost: ~$0.12/hr spot**
- $300 credit = 2,500 hours

---

## 🔑 YouTube API Quota Management

YouTube Data API v3 free quota: **10,000 units/day**

| Operation | Units | Max/day |
|---|---|---|
| videos.insert | 1,600 | **6 uploads** |
| thumbnails.set | 50 | 200 |
| captions.insert | 400 | 25 |
| videos.list | 1 | 10,000 |

**Daily safe limit: 5 video uploads** (leaves 1,950 units buffer)

To request more quota:
1. Go to GCP Console → APIs → YouTube Data API v3 → Quotas
2. Click "Edit Quotas" → Request increase
3. Explain use case — Google typically approves legitimate creators

---

## 📁 Recommended Directory Structure on GCS

```
gs://your-bucket/
├── input/          ← Raw uploads (within 5GB free tier)
│   └── *.mp4/mkv
├── output/         ← Processed YouTube-ready MP4s
├── thumbnails/     ← Generated thumbnails
├── subtitles/      ← SRT/VTT files
└── archive/        ← Move processed inputs here
```

---

## ⚡ Quick Commands Cheat Sheet

```bash
# Check free tier usage
gcloud compute instances list

# Check disk usage
df -h ~/yt-pipeline/

# Check GCS usage
gsutil du -sh gs://YOUR_BUCKET/

# View billing
open https://console.cloud.google.com/billing

# Stop VM to save credits
gcloud compute instances stop INSTANCE_NAME --zone=ZONE

# Check remaining credit
# GCP Console → Billing → Credits
```

---

## 🛡️ Safety Checklist

- [ ] Budget alert set at $50/$150/$250
- [ ] VM stops automatically after processing (add `gcloud instances stop $VM` to end of pipeline)
- [ ] Using e2-micro free tier for daily use
- [ ] YouTube API quota monitoring on
- [ ] Spot/preemptible VM used for heavy batch jobs
- [ ] Cloud Storage within 5GB free tier
- [ ] Swap space added to e2-micro (prevents OOM on large videos)
