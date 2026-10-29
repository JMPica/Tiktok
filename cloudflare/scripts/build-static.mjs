// Empaqueta public/ dentro del Worker (src/static.generated.js). Lo ejecuta wrangler antes de `dev` y `deploy`.
// Evita depender de la subida de Workers Assets y permite servir la web con cabeceras de seguridad propias.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml', '.json': 'application/json', '.txt': 'text/plain; charset=utf-8' };
const files = {};
for (const name of fs.readdirSync(path.join(root, 'public'))) {
  const ext = path.extname(name);
  if (!types[ext]) continue;
  files['/' + name] = { type: types[ext], body: fs.readFileSync(path.join(root, 'public', name), 'utf8') };
}
files['/'] = files['/index.html'];
fs.writeFileSync(path.join(root, 'src', 'static.generated.js'),
  '// GENERADO por scripts/build-static.mjs — no editar.\nexport default ' + JSON.stringify(files) + ';\n');
console.log('static:', Object.keys(files).join(' '));
