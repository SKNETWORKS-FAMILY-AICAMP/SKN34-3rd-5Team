// Client-side preparation only. The backend must independently validate uploads.
export async function prepareProfileImage(file: File): Promise<string> {
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("JPG, PNG, WebP 사진만 선택할 수 있어요.");
  if (!file.size || file.size > 5 * 1024 * 1024) throw new Error("5MB 이하의 사진을 선택해 주세요.");
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    try { await image.decode(); } catch { throw new Error("읽을 수 없는 사진이에요. 다른 파일을 선택해 주세요."); }
    const { naturalWidth: width, naturalHeight: height } = image;
    if (width < 64 || height < 64) throw new Error("가로·세로 64px 이상의 사진을 선택해 주세요.");
    if (width > 10000 || height > 10000 || width * height > 40000000) throw new Error("해상도가 너무 커요. 4천만 화소 이하, 각 변 10,000px 이하로 줄여 주세요.");
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 512;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("이 브라우저에서 사진을 처리하지 못했어요.");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, 512, 512);
    const side = Math.min(width, height);
    context.drawImage(image, (width - side) / 2, (height - side) / 2, side, side, 0, 0, 512, 512);
    // Re-encode pixels so original metadata and filename are not persisted.
    return canvas.toDataURL("image/jpeg", 0.85);
  } finally { URL.revokeObjectURL(url); }
}
