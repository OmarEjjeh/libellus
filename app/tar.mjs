// Reading the texmf tree out of one archive.
//
// The tree is ~1 800 files. Fetching them individually would be that many HTTP
// requests on a cold visit and that many OPFS handles on a warm one, so the
// Toolchain ships one uncompressed tar and this unpacks it in memory. Plain
// USTAR is a few dozen lines and saves pulling in a dependency for it.

const BLOCK = 512;

const decoder = new TextDecoder();

/** A NUL-terminated field, as tar writes them. */
function field(bytes, offset, length) {
  const slice = bytes.subarray(offset, offset + length);
  const end = slice.indexOf(0);
  return decoder.decode(end === -1 ? slice : slice.subarray(0, end)).trim();
}

/**
 * Unpack a tar archive.
 *
 * @param {ArrayBuffer} buffer
 * @returns {Array<{name: string, data: Uint8Array}>} regular files only —
 *   directories are implied by the paths and created on demand by the caller,
 *   which is what every consumer here wants anyway.
 */
export function untar(buffer) {
  const bytes = new Uint8Array(buffer);
  const files = [];
  let offset = 0;

  while (offset + BLOCK <= bytes.length) {
    const header = bytes.subarray(offset, offset + BLOCK);
    const name = field(header, 0, 100);
    if (name === "") break; // two zero blocks end the archive

    const size = parseInt(field(header, 124, 12) || "0", 8);
    const typeflag = field(header, 156, 1);
    // USTAR splits long paths; the prefix goes in front, not behind.
    const prefix = field(header, 345, 155);
    const path = prefix ? `${prefix}/${name}` : name;

    offset += BLOCK;
    // "0" and "" are both a regular file; anything else (directory, symlink,
    // the GNU extensions) carries no bytes we need.
    if (typeflag === "0" || typeflag === "") {
      files.push({ name: path, data: bytes.subarray(offset, offset + size) });
    }
    offset += Math.ceil(size / BLOCK) * BLOCK;
  }
  return files;
}
