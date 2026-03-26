<?php
// myBay - OAuth Callback Redirect
// Hosted at: https://notes.laloadrianmorales.com/ebay/callback
// Forwards eBay's auth code back to the local desktop app.
header("Location: http://localhost:8000/ebay/callback?" . $_SERVER['QUERY_STRING']);
exit;
