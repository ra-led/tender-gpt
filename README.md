# tender-gpt

## How to Use:
1. First initialize the DB:
   ```bash
   sudo docker compose exec -it web flask init-db
   ```
2. Then seed your data:
   ```bash
   sudo docker compose exec -it web flask seed-db
   ```
3. Index text data
   ```bash
   ocker-compose exec -it web flask index-tenders
   ```
4. Run your app as normal:
   ```bash
   python app.py
   ```

## Upload
```bash
sudo chmod -R u+rwX /home/yura/tender-gpt/data/
```

```bash
rsync -avz -e "ssh -i path/to/pub" /path/to/upload/ user@192.168.XXX.XXX:/path/to/data/ --rsync-path="sudo rsync"
```

