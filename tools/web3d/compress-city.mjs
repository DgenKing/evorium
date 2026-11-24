// Compress the city writer's packed streams without changing vertex or index topology.
import fs from 'node:fs';
import {MeshoptEncoder} from 'meshoptimizer';

const [source, destination] = process.argv.slice(2);
const input = fs.readFileSync(source);
const jsonBytes = input.readUInt32LE(12);
const doc = JSON.parse(input.toString('utf8', 20, 20 + jsonBytes));
const payload = input.subarray(28 + jsonBytes);
const chunks = [];
let size = 0, fallbackBytes = 0;
function add(bytes) {
  const padding = (4 - size % 4) % 4;
  chunks.push(Buffer.alloc(padding), bytes);
  size += padding;
  const offset = size;
  size += bytes.length;
  return offset;
}
await MeshoptEncoder.ready;
const views = doc.bufferViews;
const accessors = new Map(doc.accessors.map(accessor => [accessor.bufferView, accessor]));
const components = {SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4};
const componentBytes = {5120: 1, 5121: 1, 5125: 4, 5126: 4};
for (const [index, view] of views.entries()) {
  const start = view.byteOffset || 0;
  const original = payload.subarray(start, start + view.byteLength);
  const accessor = accessors.get(index);
  if (!accessor || original.length < 256) {
    view.byteOffset = add(original);
    continue;
  }
  const byteStride = view.byteStride || componentBytes[accessor.componentType] * components[accessor.type];
  const mode = view.target === 34963 ? 'TRIANGLES' : 'ATTRIBUTES';
  const filter = accessor.componentType === 5126 ? 'EXPONENTIAL' : null;
  const data = filter ? MeshoptEncoder.encodeFilterExp(new Float32Array(Uint8Array.from(original).buffer),
    accessor.count, byteStride, accessor.type === 'VEC2' ? 14 : 16) : original;
  const compressed = MeshoptEncoder.encodeGltfBuffer(data, accessor.count, byteStride, mode);
  if (compressed.length + 120 >= original.length) {
    view.byteOffset = add(original);
    continue;
  }
  view.extensions = {EXT_meshopt_compression: {buffer: 0, byteOffset: add(compressed),
    byteLength: compressed.length, byteStride, count: accessor.count, mode}};
  if (filter) view.extensions.EXT_meshopt_compression.filter = filter;
  view.buffer = 1;
  fallbackBytes += (4 - fallbackBytes % 4) % 4;
  view.byteOffset = fallbackBytes;
  fallbackBytes += view.byteLength;
}
if (fallbackBytes) {
  doc.extensionsUsed = [...(doc.extensionsUsed || []), 'EXT_meshopt_compression'];
  doc.extensionsRequired = [...(doc.extensionsRequired || []), 'EXT_meshopt_compression'];
  doc.buffers.push({byteLength: fallbackBytes, extensions: {EXT_meshopt_compression: {fallback: true}}});
}
const bin = Buffer.concat([...chunks, Buffer.alloc((4 - size % 4) % 4)]);
doc.buffers[0].byteLength = bin.length;
const json = Buffer.from(JSON.stringify(doc));
const padded = Buffer.concat([json, Buffer.alloc((4-json.length%4)%4, 32)]);
const header = Buffer.alloc(20);
header.write('glTF');
header.writeUInt32LE(2, 4);
header.writeUInt32LE(28 + padded.length + bin.length, 8);
header.writeUInt32LE(padded.length, 12);
header.write('JSON', 16);
const binHeader = Buffer.alloc(8);
binHeader.writeUInt32LE(bin.length);
binHeader.write('BIN\0', 4);
fs.writeFileSync(destination, Buffer.concat([header, padded, binHeader, bin]));
