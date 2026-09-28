// Compresses a question-image upload to WebP client-side before it ever reaches the network
// (spec: longest side <= 1600px, final file <= 800KB — matches storage_r2.py's server-side
// "question_image" limit, which still re-validates by magic bytes regardless of what the client
// claims). Quality steps down until the size target is hit or we run out of steam.
const MAX_DIMENSION = 1600;
const MAX_BYTES = 800_000;
const QUALITY_STEPS = [0.85, 0.75, 0.65, 0.55, 0.45, 0.35];

export async function compressImageToWebp(file: File): Promise<File> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_DIMENSION / Math.max(bitmap.width, bitmap.height));
  const width = Math.round(bitmap.width * scale);
  const height = Math.round(bitmap.height * scale);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D context unavailable");
  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close?.();

  let blob: Blob | null = null;
  for (const quality of QUALITY_STEPS) {
    blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", quality));
    if (blob && blob.size <= MAX_BYTES) break;
  }
  if (!blob) throw new Error("WebP compression failed");

  const newName = file.name.replace(/\.[^.]+$/, "") + ".webp";
  return new File([blob], newName, { type: "image/webp" });
}
