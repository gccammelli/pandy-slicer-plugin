plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

// The slicing engine (engine/README.md): Bambu Studio's command-line slicer for arm64, a static executable. Android
// only lets apps run executables installed as native libraries, so it ships as lib/arm64-v8a/libpandy_engine.so;
// its profiles and data ship as an asset archive the app unpacks once (engine/package-android.sh builds both).
val engineDir = rootProject.layout.projectDirectory.dir("build/android-engine")

android {
    namespace = "io.github.gccammelli.pandystudio"
    compileSdk = 37

    defaultConfig {
        applicationId = "io.github.gccammelli.pandy.slicer" + if (providers.gradleProperty("pandy.testbed").isPresent) ".testbed" else ""
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        ndk { abiFilters += "arm64-v8a" }
    }

    sourceSets.getByName("main") {
        jniLibs.directories += engineDir.dir("jniLibs").asFile.path
        assets.directories += engineDir.dir("assets").asFile.path
    }

    // Executables must be extracted to the native library directory to be runnable.
    packaging.jniLibs.useLegacyPackaging = true
    androidResources.noCompress += "zip"

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures { compose = true; buildConfig = true }

    dependenciesInfo { includeInApk = false; includeInBundle = false }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(project(":shared"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.foundation)
    implementation(libs.compose.material3)
    implementation(libs.kotlinx.coroutines.android)
}
