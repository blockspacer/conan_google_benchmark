from conans import ConanFile, CMake, tools
import os

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

class TestPackageConan(conan_build_helper.CMakePackage):
    name = "conan_benchmark_test_package"
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"

    # sets cmake variables required to use clang 10 from conan
    def _is_compile_with_llvm_tools_enabled(self):
      return self._environ_option("COMPILE_WITH_LLVM_TOOLS", default = 'false')

    # installs clang 10 from conan
    def _is_llvm_tools_enabled(self):
      return self._environ_option("ENABLE_LLVM_TOOLS", default = 'false')

    def build_requirements(self):
        self.build_requires("cmake_platform_detection/master@conan/stable")
        self.build_requires("cmake_build_options/master@conan/stable")
        self.build_requires("cmake_helper_utils/master@conan/stable")

        if self.options['benchmark'].enable_tsan \
            or self.options['benchmark'].enable_msan \
            or self.options['benchmark'].enable_asan \
            or self.options['benchmark'].enable_ubsan:
          self.build_requires("cmake_sanitizers/master@conan/stable")

        # provides clang-tidy, clang-format, IWYU, scan-build, etc.
        if self._is_llvm_tools_enabled():
          self.build_requires("llvm_tools/master@conan/stable")

    def build(self):
        cmake = CMake(self)

        cmake.definitions['ENABLE_UBSAN'] = self.options['benchmark'].enable_ubsan
        cmake.definitions['ENABLE_ASAN'] = self.options['benchmark'].enable_asan
        cmake.definitions['ENABLE_MSAN'] = self.options['benchmark'].enable_msan
        cmake.definitions['ENABLE_TSAN'] = self.options['benchmark'].enable_tsan

        self.add_cmake_option(cmake, "COMPILE_WITH_LLVM_TOOLS", self._is_compile_with_llvm_tools_enabled())


        cmake.configure()
        cmake.build()

    def test(self):
        if not tools.cross_building(self.settings):
            #bin_path = os.path.join("bin", "test_package")
            #self.run(bin_path, run_environment=True)
            bin_path = os.path.join(self.build_folder, "test_package")
            self.run(bin_path, run_environment=True)
