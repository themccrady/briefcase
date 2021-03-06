import json
import os
import shutil
import sys

import subprocess

from .app import app


class ios(app):
    description = "Create an iOS app to wrap this project"

    def finalize_options(self):
        # Copy over all the options from the base 'app' command
        finalized = self.get_finalized_command('app')
        for attr in ('formal_name', 'organization_name', 'bundle', 'icon', 'splash', 'download_dir'):
            if getattr(self, attr) is None:
                setattr(self, attr, getattr(finalized, attr))

        super(ios, self).finalize_options()

        # Set platform-specific options
        self.platform = 'iOS'
        self.support_project = "Python-Apple-support"

        self.device = None

        if self.dir is None:
            self.dir = self.platform

        self.resource_dir = self.dir

    def install_icon(self):
        last_size = None
        for size in ['180', '167', '152', '120', '87', '80', '76', '58', '40', '29']:
            icon_file = '%s-%s.png' % (self.icon, size)
            if os.path.exists(icon_file):
                last_size = size
            else:
                if last_size:
                    print("WARNING: No %sx%s icon file available; using %sx%s" % (size, size, last_size, last_size))
                    icon_file = '%s-%s.png' % (self.icon, last_size)
                else:
                    icon_file = None

            if icon_file:
                shutil.copyfile(
                    icon_file,
                    os.path.join(self.resource_dir, self.distribution.get_name(), 'Images.xcassets', 'AppIcon.appiconset', 'icon-%s.png' % size)
                )
            else:
                print("WARNING: No %sx%s icon file available." % (size, size))

    def install_splash(self):
        for size in ['1024x768', '1536x2048', '2048x1536', '768x1024', '640x1136', '640x960']:
            splash_file = '%s-%s.png' % (self.splash, size)

            if os.path.exists(splash_file):
                shutil.copyfile(
                    splash_file,
                    os.path.join(self.resource_dir, self.distribution.get_name(), 'Images.xcassets', 'LaunchImage.launchimage', 'launch-%s.png' % size)
                )
            else:
                print("WARNING: No %s splash file available." % size)

    def set_device_target(self):
        if self.os_version is None or self.device_name is None or self.device is None:
            # Find an appropriate device
            pipe = subprocess.Popen(['xcrun', 'simctl', 'list', '-j'], stdout=subprocess.PIPE)
            pipe.wait()

            data = json.loads(pipe.stdout.read().decode())

            if self.os_version is None:
                os_list = [label for label in data['devices'] if label.startswith('iOS')]
                if len(os_list) == 0:
                    print('No iOS device simulators found', file=sys.stderr)
                    sys.exit(1)
                elif len(os_list) == 1:
                    print('Building for %s...' % os_list[0])
                    self.os_version = os_list[0]
                else:
                    print()
                    while self.os_version is None:
                        print('Available iOS versions:')
                        for i, label in enumerate(os_list):
                            print('  [%s] %s' % (i+1, label))
                        index = int(input('Which iOS version do you want to target: '))
                        try:
                            self.os_version = os_list[int(index) - 1]
                        except:
                            print("Invalid selection.")
                            print

            if self.device_name is None:
                device_list = data['devices'].get(self.os_version, [])
                if len(device_list) == 0:
                    print('No %s devices found', file=sys.stderr)
                    sys.exit(2)
                elif len(device_list) == 1:
                    print('Device ID is %s...' % device_list[0])
                    self.device = device_list[0]
                    self.device_name = device['name']
                else:
                    print()
                    while self.device_name is None:
                        print('Available devices:')
                        for i, device in enumerate(device_list):
                            print('  [%s] %s' % (i+1, device['name']))
                        index = int(input('Which device do you want to target: '))
                        try:
                            self.device = device_list[int(index) - 1]
                            self.device_name = device['name']
                        except:
                            print("Invalid selection.")
                            print

            if self.device is None:
                device_list = data['devices'].get(self.os_version, [])
                self.device = [x for x in device_list if x['name'].lower() == self.device_name.lower()][0]

    def has_required_xcode_version(self):
        pipe = subprocess.Popen(['xcrun', 'xcodebuild', '-version'], stdout=subprocess.PIPE)
        pipe.wait()

        output = pipe.stdout.read().decode()
        version = tuple(
            int(v)
            for v in output.split('\n')[0].split(' ')[1].split('.')[:2]
        )
        if version < (8, 0):
            print('\nAutomated builds require XCode 8.0 or later', file=sys.stderr)
            return False
        else:
            return True

    def build_app(self):
        if not self.has_required_xcode_version():
            return

        project_file = '%s.xcodeproj' % self.formal_name
        build_settings = [
            ('AD_HOC_CODE_SIGNING_ALLOWED', 'YES'),
            ('CODE_SIGN_IDENTITY', '-'),
            ('VALID_ARCHS', '"i386 x86_64"'),
            ('ARCHS', 'x86_64'),
            ('ONLY_ACTIVE_ARCHS', 'NO')
        ]
        build_settings_str = ['%s=%s' % x for x in build_settings]

        self.set_device_target()

        print(' * Building XCode project for %s %s...' % (self.device_name, self.os_version))

        subprocess.Popen([
            'xcodebuild', ' '.join(build_settings_str), '-project', project_file, '-destination',
            'platform="iOS Simulator,name=%s,OS=%s"' % (self.device_name, self.os_version), '-quiet', '-configuration',
            'Debug', '-arch', 'x86_64', '-sdk', 'iphonesimulator%s' % (self.os_version.split(' ')[-1],), 'build'
        ], cwd=os.path.abspath(self.dir)).wait()

    def start_app(self):
        if not self.has_required_xcode_version():
            return

        working_dir = os.path.abspath(self.dir)

        self.set_device_target()

        # Install app and launch simulator
        app_identifier = '.'.join([self.bundle, self.formal_name.replace(' ', '-')])

        print()
        print("Starting app on %s %s" % (self.device_name, self.os_version))
        print(' * Starting simulator...')
        subprocess.Popen(
            ['instruments', '-w', self.device['udid']],
            stderr=subprocess.PIPE
        ).communicate()

        print(' * Uninstalling old app version...')
        subprocess.Popen(
            ['xcrun', 'simctl', 'uninstall', self.device['udid'], app_identifier],
            cwd=working_dir
        ).wait()

        print(' * Installing new app version...')
        subprocess.Popen([
            'xcrun', 'simctl', 'install', self.device['udid'],
            os.path.join('build', 'Debug-iphonesimulator', '%s.app' % self.formal_name)
        ], cwd=working_dir).wait()

        print(' * Launching app...')
        subprocess.Popen([
            'xcrun', 'simctl', 'launch', self.device['udid'], app_identifier
        ]).wait()
