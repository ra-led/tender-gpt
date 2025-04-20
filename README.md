# tender-gpt

## How to Use:
1. First initialize the DB:
   ```bash
   flask init-db
   ```
2. Then seed your data:
   ```bash
   flask seed-db
   ```
3. Run your app as normal:
   ```bash
   python app.py
   ```

## Upload
```bash
sudo chmod -R u+rwX /home/yura/tender-gpt/data/
```

```bash
rsync -avz -e "ssh -i /Users/yuratomakov/soft/repo/ds-scripts/rag-conversational-agent/mvd" /Users/yuratomakov/zakupki-gov/upload/ yura@158.160.51.157:/home/yura/tender-gpt/data/ --rsync-path="sudo rsync"
```

