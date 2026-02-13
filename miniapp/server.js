import express from 'express';
import compression from 'compression';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const port = process.env.PORT || 3001;

// Enable gzip compression
app.use(compression());

// Serve static files from dist directory
app.use(express.static(join(__dirname, 'dist')));

// Handle all routes - return index.html
app.get('*', (req, res) => {
  res.sendFile(join(__dirname, 'dist', 'index.html'));
});

app.listen(port, () => {
  console.log(`Design Community Mini App running on port ${port}`);
});
