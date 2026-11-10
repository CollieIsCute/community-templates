# Mattermost

Requires Python 3 and a Mattermost personal access token.

1. In Mattermost, open **Profile -> Security -> Personal Access Tokens** and create a token. If this option is missing, ask your administrator to enable it.
2. Create a private credentials file:

   ```sh
   install -d -m 700 "${XDG_CONFIG_HOME:-$HOME/.config}/noctalia-mattermost"
   touch "${XDG_CONFIG_HOME:-$HOME/.config}/noctalia-mattermost/credentials.json"
   chmod 600 "${XDG_CONFIG_HOME:-$HOME/.config}/noctalia-mattermost/credentials.json"
   ```

3. Edit that file with your server URL and token:

   ```json
   {
     "url": "https://mattermost.example.com",
     "token": "YOUR_PERSONAL_ACCESS_TOKEN"
   }
   ```

4. Enable **Mattermost** in **Noctalia Settings -> Templates**.

After changing the credentials, run `noctalia msg templates-apply`.

Disable the template before deleting the credentials so your previous theme can be restored.
