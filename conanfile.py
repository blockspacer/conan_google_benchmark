from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration
import os

from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration
import os
import glob

import glob
import os
from conans import ConanFile, CMake, tools
from conans.model.version import Version
from conans.errors import ConanInvalidConfiguration

from conans import ConanFile, CMake, tools, AutoToolsBuildEnvironment, RunEnvironment, python_requires
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.tools import os_info
import os, re, stat, fnmatch, platform, glob, traceback, shutil
from functools import total_ordering

# if you using python less than 3 use from distutils import strtobool
from distutils.util import strtobool

conan_build_helper = python_requires("conan_build_helper/[~=0.0]@conan/stable")

# Users locally they get the 1.0.0 version,
# without defining any env-var at all,
# and CI servers will append the build number.
# USAGE
# version = get_version("1.0.0")
# BUILD_NUMBER=-pre1+build2 conan export-pkg . my_channel/release
def get_version(version):
    bn = os.getenv("BUILD_NUMBER")
    return (version + bn) if bn else version

class BenchmarkConan(conan_build_helper.CMakePackage):
    name = "benchmark"
    description = "A microbenchmark support library."
    topics = ("conan", "benchmark", "google", "microbenchmark")
    url = "https://github.com/conan-io/conan-center-index/"
    repo_url = 'https://github.com/google/benchmark'
    homepage = "https://github.com/google/benchmark"
    license = "Apache-2.0"
    exports_sources = ["CMakeLists.txt"]
    generators = "cmake"
    version = get_version("v1.5.2")

    settings = "arch", "build_type", "compiler", "os"

    options = {
      "enable_ubsan": [True, False],
      "enable_asan": [True, False],
      "enable_msan": [True, False],
      "enable_tsan": [True, False],
      "shared": [True, False],
      "fPIC": [True, False],
      "enable_lto": [True, False],
      "enable_exceptions": [True, False]
    }

    default_options = {
      "enable_ubsan": False,
      "enable_asan": False,
      "enable_msan": False,
      "enable_tsan": False,
      "shared": False,
      "fPIC": True,
      "enable_lto": False,
      "enable_exceptions": True
    }

    # sets cmake variables required to use clang 10 from conan
    def _is_compile_with_llvm_tools_enabled(self):
      return self._environ_option("COMPILE_WITH_LLVM_TOOLS", default = 'false')

    # installs clang 10 from conan
    def _is_llvm_tools_enabled(self):
      return self._environ_option("ENABLE_LLVM_TOOLS", default = 'false')

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _build_subfolder(self):
        return "build_subfolder"

    @property
    def _libcxx(self):
      return str(self.settings.get_safe("compiler.libcxx"))

    _cmake = None

    def source(self):
#        tools.get(**self.conan_data["sources"][self.version])
#        extracted_dir = self.name + "-" + self.version
#        os.rename(extracted_dir, self._source_subfolder)
        self.run('git clone --progress --branch {} --recursive --recurse-submodules {} {}'.format(self.version, self.repo_url, self._source_subfolder))

    def config_options(self):
        if self.settings.os == "Windows":
            if self.settings.compiler == "Visual Studio" and tools.Version(self.settings.compiler.version.value) <= 12:
                raise ConanInvalidConfiguration("{} {} does not support Visual Studio <= 12".format(self.name, self.version))
            del self.options.fPIC

    def configure(self):
        lower_build_type = str(self.settings.build_type).lower()

        if lower_build_type != "release" and not self._is_llvm_tools_enabled():
            self.output.warn('enable llvm_tools for Debug builds')

        if self._is_compile_with_llvm_tools_enabled() and not self._is_llvm_tools_enabled():
            raise ConanInvalidConfiguration("llvm_tools must be enabled")

        if self.options.enable_ubsan \
           or self.options.enable_asan \
           or self.options.enable_msan \
           or self.options.enable_tsan:
            if not self._is_llvm_tools_enabled():
                raise ConanInvalidConfiguration("sanitizers require llvm_tools")

        if self.settings.os == "Windows" and self.options.shared:
            raise ConanInvalidConfiguration("Windows shared builds are not supported right now, see issue #639")

    def _configure_cmake(self):
        if self._cmake:
            return self._cmake
        self._cmake = CMake(self)

        self._cmake.definitions["ENABLE_UBSAN"] = 'ON'
        if not self.options.enable_ubsan:
            self._cmake.definitions["ENABLE_UBSAN"] = 'OFF'

        self._cmake.definitions["ENABLE_ASAN"] = 'ON'
        if not self.options.enable_asan:
            self._cmake.definitions["ENABLE_ASAN"] = 'OFF'

        self._cmake.definitions["ENABLE_MSAN"] = 'ON'
        if not self.options.enable_msan:
            self._cmake.definitions["ENABLE_MSAN"] = 'OFF'

        self._cmake.definitions["ENABLE_TSAN"] = 'ON'
        if not self.options.enable_tsan:
            self._cmake.definitions["ENABLE_TSAN"] = 'OFF'

        self.add_cmake_option(self._cmake, "COMPILE_WITH_LLVM_TOOLS", self._is_compile_with_llvm_tools_enabled())

        self._cmake.definitions["BENCHMARK_ENABLE_TESTING"] = "OFF"
        self._cmake.definitions["BENCHMARK_ENABLE_GTEST_TESTS"] = "OFF"
        self._cmake.definitions["BENCHMARK_ENABLE_LTO"] = "ON" if self.options.enable_lto else "OFF"
        self._cmake.definitions["BENCHMARK_ENABLE_EXCEPTIONS"] = "ON" if self.options.enable_exceptions else "OFF"

        # See https://github.com/google/benchmark/pull/638 for Windows 32 build explanation
        if self.settings.os != "Windows":
            if tools.cross_building(self.settings):
                self._cmake.definitions["HAVE_STD_REGEX"] = False
                self._cmake.definitions["HAVE_POSIX_REGEX"] = False
                self._cmake.definitions["HAVE_STEADY_CLOCK"] = False
            else:
                self._cmake.definitions["BENCHMARK_BUILD_32_BITS"] = "ON" if "64" not in str(self.settings.arch) else "OFF"
            self._cmake.definitions["BENCHMARK_USE_LIBCXX"] = "ON" if (self._libcxx == "libc++") else "OFF"
        else:
            self._cmake.definitions["BENCHMARK_USE_LIBCXX"] = "OFF"

        self._cmake.configure(build_folder=self._build_subfolder)
        return self._cmake

    def build_requirements(self):
        self.build_requires("cmake_platform_detection/master@conan/stable")
        self.build_requires("cmake_build_options/master@conan/stable")
        self.build_requires("cmake_helper_utils/master@conan/stable")

        if self.options.enable_tsan \
            or self.options.enable_msan \
            or self.options.enable_asan \
            or self.options.enable_ubsan:
          self.build_requires("cmake_sanitizers/master@conan/stable")

        # provides clang-tidy, clang-format, IWYU, scan-build, etc.
        if self._is_llvm_tools_enabled():
          self.build_requires("llvm_tools/master@conan/stable")

    def build(self):
        cmake = self._configure_cmake()
        cmake.build()

    def package(self):
        cmake = self._configure_cmake()
        cmake.install()

        self.copy(pattern="LICENSE", dst="licenses", src=self._source_subfolder)
        tools.rmdir(os.path.join(self.package_folder, 'lib', 'pkgconfig'))
        tools.rmdir(os.path.join(self.package_folder, 'lib', 'cmake'))

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
        if self.settings.os == "Linux":
            self.cpp_info.system_libs.extend(["pthread", "rt"])
        elif self.settings.os == "Windows":
            self.cpp_info.system_libs.append("shlwapi")
        elif self.settings.os == "SunOS":
            self.cpp_info.system_libs.append("kstat")
