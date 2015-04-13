# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2014-2015, Lars Asplund lars.anders.asplund@gmail.com

"""
Interface towards NVC simulator
https://github.com/nickg/nvc
"""

from __future__ import print_function
import os
from os.path import dirname, exists, join
import subprocess
from vunit.simulator_interface import SimulatorInterface
from vunit.exceptions import CompileError
from vunit.ostools import Process


class NvcInterface(SimulatorInterface):
    """
    Interface towards NVC simulator
    """
    name = "nvc"

    @staticmethod
    def add_arguments(parser):
        """
        Add command line arguments
        """
        pass

    @classmethod
    def from_args(cls, output_path, args):  # pylint: disable=unused-argument
        return cls(prefix=cls.find_prefix())

    @classmethod
    def find_prefix_from_path(cls):
        """
        Find nvc executable prefix from PATH environment variable
        """
        return cls.find_toolchain(['nvc'])

    def __init__(self, prefix):
        self._prefix = prefix
        self._libraries = {}
        self._vhdl_standard = None

    def setup_library_mapping(self, project):
        """
        Setup the library mapping according to project
        """

        vhdl_standards = set(source_file.get_vhdl_standard()
                             for source_file in project.get_source_files_in_order()
                             if source_file.file_type is 'vhdl')

        if len(vhdl_standards) == 0:
            self._vhdl_standard = '2008'
        elif len(vhdl_standards) != 1:
            raise RuntimeError("NVC cannot handle mixed VHDL standards, found %r" % list(vhdl_standards))
        else:
            self._vhdl_standard = list(vhdl_standards)[0]

        libraries = project.get_libraries()
        self._libraries = libraries
        for library in libraries:
            if not exists(dirname(library.directory)):
                os.makedirs(dirname(library.directory))
            args = ['--std=%s' % self._vhdl_standard]
            args += ['--ignore-time']
            args += ['--work=%s:%s' % (library.name, library.directory)]
            args += ['-a']
            subprocess.check_output([join(self._prefix, 'nvc')] + args)

    def compile_source_file_command(self, source_file):
        """
        Returns command to compile source file
        """
        if source_file.file_type == 'vhdl':
            return self.compile_vhdl_file_command(source_file)

        raise CompileError

    def compile_vhdl_file_command(self, source_file):
        """
        Returns the commands to compile a vhdl file
        """
        args = [join(self._prefix, 'nvc'), '--std=%s' % self._vhdl_standard]
        args += ['--ignore-time']
        for library in self._libraries:
            args += ['--map=%s:%s' % (library.name, library.directory)]
            if library.name == source_file.library.name:
                args += ['--work=%s:%s' % (library.name, library.directory)]
        args += ['-a', source_file.name]

        design_units_to_codegen = set()

        for design_unit in source_file.design_units:
            if design_unit.unit_type in ("package", "package body"):
                design_units_to_codegen.add(design_unit.name)
        for name in sorted(design_units_to_codegen):
            args += ['--codegen', name]
        return args

    def simulate(self, output_path, test_suite_name, config, elaborate_only):
        """
        Simulate top level
        """
        # @TODO disable_ieee_warnings
        try:
            args = []
            args += ['--std=%s' % "2008"]
            args += ['--ignore-time']
            for library in self._libraries:
                args += ['--map=%s:%s' % (library.name, library.directory)]
                if library.name == config.library_name:
                    args += ['--work=%s:%s' % (library.name, library.directory)]
            args += ['--work', config.library_name]
            args += ['-e', config.entity_name, config.architecture_name]
            for item in config.generics.items():
                args += ['-g%s=%s' % item]

            if elaborate_only:
                proc = Process([join(self._prefix, 'nvc')] + args)
                proc.consume_output()
                return True

            args += ['-r', config.entity_name, config.architecture_name]
            args += ["--exit-severity=%s" % config.vhdl_assert_stop_level]

            proc = Process([join(self._prefix, 'nvc')] + args)
            proc.consume_output()

        except Process.NonZeroExitCode:
            return False

        return True
