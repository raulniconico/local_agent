// Copy to `config.js` and fill in. That file is git-ignored, the same way
// coffee_android/v1/local.properties and coffee_server/.env are: the OAuth
// client ID is not a secret -- it identifies the app to Google and is visible
// in every consent URL -- but it is account-identifying, so this project keeps
// it out of the repository along with the gateway host.
//
// `deploy.sh` rsyncs this directory as it stands, so the file ships from your
// machine. Without it, /delete explains itself and offers the email route
// instead of failing silently.
window.COFFEE_CAN = {
  // The gateway. Must end in a slash.
  API_BASE: "https://api.example.com/",
  // The OAuth *web* client ID -- the same GOOGLE_SERVER_CLIENT_ID the app
  // sends and the gateway checks the token's audience against. This origin
  // must be listed under "Authorised JavaScript origins" for that client in
  // the Google Cloud console, or sign-in here fails with origin_mismatch.
  GOOGLE_CLIENT_ID: "",
};
