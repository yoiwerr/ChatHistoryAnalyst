# Deployment TODO

Server: 阿里云/腾讯云 Ubuntu 20.04/22.04, public IP

## 1. Server setup (SSH into server)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker $USER
newgrp docker

# Install docker compose plugin
sudo apt update && sudo apt install docker-compose-plugin

# Allow port 80 in firewall (阿里云还需要在控制台安全组开放 80 端口)
sudo ufw allow 80/tcp
```

## 2. Deploy the project

```bash
# Clone project to server
git clone <your-repo-url> ~/ChatHistoryAnalyst
cd ~/ChatHistoryAnalyst

# Run deploy script (creates .env, builds, starts)
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

## 3. Verify

```bash
# Check all containers running
docker compose ps

# Test portfolio
curl http://localhost

# Test API
curl http://localhost/api/v1/imported_files
```

Then open browser: `http://<server-public-ip>`

## 4. After first deploy

- Portfolio available at `http://<ip>/`
- ChatLab available at `http://<ip>/chatlab`
- API docs at `http://<ip>/api/docs`

## 5. Security checklist (before long-term use)

- [ ] Set strong PostgreSQL password in `.env`
- [ ] 阿里云安全组: only open port 80 (and 22 for SSH)
- [ ] Setup HTTPS with Let's Encrypt + Certbot when you get a domain
- [ ] Regular backup: `docker compose exec postgres pg_dump -U postgres chatdemopg > backup.sql`
