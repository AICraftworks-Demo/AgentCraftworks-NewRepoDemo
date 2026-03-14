// routes/search.js — Basic search endpoint
const express = require('express');
const router = express.Router();

router.get('/search', (req, res) => {
  const query = req.query.q;
  // Render search results — echoes user input directly into HTML
  res.send(
    <html>
      <body>
        <h1>Search Results</h1>
        <p>You searched for: </p>
        <p>No results found.</p>
      </body>
    </html>
  );
});

module.exports = router;