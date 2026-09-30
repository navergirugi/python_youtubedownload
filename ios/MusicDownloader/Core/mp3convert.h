#ifndef MDL_MP3CONVERT_H
#define MDL_MP3CONVERT_H

#ifdef __cplusplus
extern "C" {
#endif

/* Bundle the statically linked libav (AAC/Opus decode + libmp3lame encode)
 * to convert any decodable audio file to MP3. iOS forbids spawning an
 * ffmpeg binary, so this runs in-process.
 * Returns 0 on success, 1 no audio stream, 2 encoder missing, 3 I/O error,
 * or a negative libav error code. */
int mdl_convert_to_mp3(const char *src_path, const char *dst_path, int bitrate_kbps);

#ifdef __cplusplus
}
#endif

#endif
