# Keep rules (debug build does not minify; release placeholder)
-keep class com.musicdownloader.** { *; }
-dontwarn org.schabi.newpipe.**
-dontwarn com.arthenica.**

# ffmpeg-kit 이 예외 포맷팅용으로 리플렉션으로 참조한다. minify 하면 깨진다.
-keep class com.arthenica.smartexception.** { *; }
-keep class com.arthenica.ffmpegkit.** { *; }
