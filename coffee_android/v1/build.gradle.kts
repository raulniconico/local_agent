// AGP 8.9.1 is the floor for compileSdk 36 (Android 16), which
// specs/legal-android.md rule 18 requires. It in turn needs Gradle 8.11.1+ --
// generate the wrapper at that version (`gradle wrapper --gradle-version
// 8.11.1`) and build on JDK 17 or 21. JDK 25 is not supported by this
// toolchain and fails at configuration time, not with a clear message.
plugins {
    id("com.android.application") version "8.9.1" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
    // The serialization *compiler* plugin. The kotlinx-serialization-json
    // dependency alone is the runtime half; without this, every @Serializable
    // fails at compile time with "serializer has not been found".
    id("org.jetbrains.kotlin.plugin.serialization") version "2.0.21" apply false
    id("com.google.devtools.ksp") version "2.0.21-1.0.28" apply false
    // JVM-only Compose screenshot rendering (no emulator/device) -- how the
    // "-1.1"/"-1.1a" render-and-compare pass in this session's conversation
    // was done. Test-only; does not affect the shipped app.
    id("app.cash.paparazzi") version "1.3.5" apply false
}
