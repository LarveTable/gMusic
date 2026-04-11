# gMusic
My private discord music bot

## Docker

Build the image from the repository root:

```bash
docker build -t gmusic .
```

Run it with your Discord token and any other environment variables the bot expects:

```bash
docker run --rm -it --env-file .env gmusic
```
