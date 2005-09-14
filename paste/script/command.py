import pkg_resources
import sys
import optparse
import os
import pluginlib
try:
    import subprocess
except ImportError:
    pass

class BadCommand(Exception):

    def __init__(self, message, exit_code=2):
        self.message = message
        self.exit_code = exit_code
        Exception.__init__(self, message)

parser = optparse.OptionParser()
parser.add_option(
    '--plugin',
    action='append',
    dest='plugins',
    help="Add a plugin to the list of commands (plugins are Egg specs)")
parser.disable_interspersed_args()

# @@: Add an option to run this in another Python interpreter

system_plugins = ['PasteScript']

def run():
    if '_' in os.environ and 0:
        # This seems to signal a #! line
        config = os.path.abspath(os.environ['_'])
        args = parse_exe_file(config)
    else:
        args = sys.argv[1:]
    options, args = parser.parse_args(args)
    system_plugins.extend(options.plugins or [])
    commands = get_commands()
    if not args:
        print 'Usage: %s COMMAND' % sys.argv[0]
        args = ['help']
    command_name = args[0]
    if command_name not in commands:
        command = NotFoundCommand
    else:
        command = commands[command_name].load()
    invoke(command, command_name, options, args[1:])

def parse_exe_file(config):
    import ConfigParser
    import shlex
    p = ConfigParser.RawConfigParser()
    p.read([config])
    command_name = 'exe'
    options = []
    if p.has_option('exe', 'command'):
        command_name = p.get('exe', 'command')
    if p.has_option('exe', 'options'):
        options = shlex.split(p.get('exe', 'options'))
    if p.has_option('exe', 'sys.path'):
        paths = shlex.split(p.get('exe', 'sys.path'))
        paths = [os.path.abspath(os.path.join(os.path.dirname(config), p))
                 for p in paths]
        for path in paths:
            pkg_resources.working_set.add_entry(path)
            sys.path.insert(0, path)
    args = [command_name, config] + options
    return args

def get_commands():
    plugins = system_plugins[:]
    egg_info_dir = pluginlib.find_egg_info_dir(os.getcwd())
    if egg_info_dir:
        plugins.append(os.path.splitext(os.path.basename(egg_info_dir))[0])
    plugins = pluginlib.resolve_plugins(plugins)
    commands = pluginlib.load_commands_from_plugins(plugins)
    return commands

def invoke(command, command_name, options, args):
    sys.old_argv0 = sys.argv[0]
    sys.argv[0] = '%s %s' % (sys.argv[0], command_name)
    try:
        runner = command(command_name)
        exit_code = runner.run(args)
    except BadCommand, e:
        print e.message
        exit_code = e.exit_code
    sys.exit(exit_code)


class Command(object):

    def __init__(self, name):
        self.command_name = name

    max_args = None
    max_args_error = 'You must provide no more than %(max_args)s arguments'
    min_args = None
    min_args_error = 'You must provide at least %(min_args)s arguments'
    required_args = None

    aliases = ()
    required_args = ()
    description = None
    usage = ''
    hidden = False
    default_verbosity = 0
    return_code = 0

    BadCommand = BadCommand

    # Must define:
    #   parser
    #   summary
    #   command()

    def run(self, args):
        self.parse_args(args)
        
        # Setup defaults:
        if not hasattr(self.options, 'verbose'):
            self.options.verbose = 0
        if not hasattr(self.options, 'quiet'):
            self.options.quiet = 0
        if not hasattr(self.options, 'interactive'):
            self.options.interactive = 0
        if (getattr(self.options, 'simulate', False)
            and not self.options.verbose):
            self.options.verbose = max(self.options.verbose, 1)
        self.verbose = self.default_verbosity
        self.verbose += self.options.verbose
        self.verbose -= self.options.quiet
        self.interactive = self.options.interactive
        self.simulate = getattr(self.options, 'simulate', False)

        # Validate:
        if self.min_args is not None and len(self.args) < self.min_args:
            raise BadCommand(
                self.min_args_error % {'min_args': self.min_args,
                                       'actual_args': len(self.args)})
        if self.max_args is not None and len(self.args) > self.max_args:
            raise BadCommand(
                self.max_args_error % {'max_args': self.max_args,
                                       'actual_args': len(self.args)})
        for var_name, option_name in self.required_args:
            if not getattr(self.options, var_name, None):
                raise BadCommand(
                    'You must provide the option %s' % option_name)
        result = self.command()
        if result is None:
            return self.return_code
        else:
            return result

    def parse_args(self, args):
        if self.usage:
            usage = ' '+self.usage
        else:
            usage = ''
        self.parser.usage = "%%prog [options]%s\n%s" % (
            usage, self.summary)
        self.parser.prog = '%s %s' % (sys.argv[0], self.command_name)
        if self.description:
            self.parser.description = self.description
        self.options, self.args = self.parser.parse_args(args)

    ########################################
    ## Utility methods
    ########################################

    def here(cls):
        mod = sys.modules[cls.__module__]
        return os.path.dirname(mod.__file__)

    here = classmethod(here)

    def ask(self, prompt, safe=False, default=True):
        """
        Prompt the user.  Default can be true, false, ``'careful'`` or
        ``'none'``.  If ``'none'`` then the user must enter y/n.  If
        ``'careful'`` then the user must enter yes/no (long form).

        If the interactive option is over two (``-ii``) then ``safe``
        will be used as a default.  This option should be the
        do-nothing option.
        """
        # @@: Should careful be a separate argument?

        if self.options.interactive >= 2:
            default = safe
        if default == 'careful':
            prompt += ' [yes/no]?'
        elif default == 'none':
            prompt += ' [y/n]?'
        elif default:
            prompt += ' [Y/n]? '
        else:
            prompt += ' [y/N]? '
        while 1:
            response = raw_input(prompt).strip().lower()
            if not response:
                if default in ('careful', 'none'):
                    print 'Please enter yes or no'
                    continue
                return default
            if default == 'careful':
                if response in ('yes', 'no'):
                    return response == 'yes'
                print 'Please enter "yes" or "no"'
                continue
            if response[0].lower() in ('y', 'n'):
                return response[0].lower() == 'y'
            print 'Y or N please'

    def pad(self, s, length, dir='left'):
        if len(s) >= length:
            return s
        if dir == 'left':
            return s + ' '*(length-len(s))
        else:
            return ' '*(length-len(s)) + s

    def standard_parser(cls, verbose=True,
                        interactive=False,
                        simulate=False,
                        quiet=False):
        """
        Typically used like::

            class MyCommand(Command):
                parser = Command.standard_parser()

        Subclasses may redefine ``standard_parser``, so use the
        nearest superclass's class method.
        """
        parser = optparse.OptionParser()
        if verbose:
            parser.add_option('-v', '--verbose',
                              action='count',
                              dest='verbose',
                              default=0)
        if quiet:
            parser.add_option('-q', '--quiet',
                              action='count',
                              dest='quiet',
                              default=0)
        if interactive:
            parser.add_option('-i', '--interactive',
                              action='count',
                              dest='interactive',
                              default=0)
        if simulate:
            parser.add_option('-n', '--simulate',
                              action='store_true',
                              dest='simulate',
                              default=False)
                              
        return parser

    standard_parser = classmethod(standard_parser)

    def shorten(self, fn, *paths):
        """
        Return a shorted form of the filename (relative to the current
        directory), typically for displaying in messages.  If
        ``*paths`` are present, then use os.path.join to create the
        full filename before shortening.
        """
        if paths:
            fn = os.path.join(fn, *paths)
        if fn.startswith(os.getcwd()):
            return fn[len(os.getcwd()):].lstrip(os.path.sep)
        else:
            return fn

    def ensure_dir(self, dir, svn_add=True):
        """
        Ensure that the directory exists, creating it if necessary.
        Respects verbosity and simulation.

        Adds directory to subversion if ``.svn/`` directory exists in
        parent, and directory was created.
        """
        dir = dir.rstrip(os.sep)
        if not os.path.exists(dir):
            self.ensure_dir(os.path.dirname(dir))
            if self.verbose:
                print 'Creating %s' % self.shorten(dir)
            if not self.simulate:
                os.mkdir(dir)
            if (svn_add and
                os.path.exists(os.path.join(os.path.dirname(dir), '.svn'))):
                self.run_command('svn', 'add', dir)

    def run_command(self, cmd, *args):
        """
        Runs the command, respecting verbosity and simulation.
        Returns stdout, or None if simulating.
        """
        proc = subprocess.Popen([cmd] + list(args),
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE)
        if self.verbose:
            print 'Running %s %s' % (cmd, ' '.join(args))
        if self.simulate:
            return None
        stdout, stderr = proc.communicate()
        if proc.returncode:
            if not self.verbose:
                print 'Running %s %s' % (cmd, ' '.join(args))
            print 'Error (exit code: %s)' % proc.returncode
            if stderr:
                print stderr
            raise OSError("Error executing command %s" % cmd)
        if self.verbose > 2:
            if stderr:
                print 'Command error output:'
                print stderr
            if stdout:
                print 'Command output:'
                print stdout
        return stdout

    def write_file(self, filename, content, source=None,
                   binary=True, svn_add=True):
        if os.path.exists(filename):
            if binary:
                f = open(filename, 'rb')
            else:
                f = open(filename, 'r')
            old_content = f.read()
            f.close()
            if content == old_content:
                if self.verbose:
                    print 'File %s exists with same content' % (
                        self.shorten(filename))
                return
            if (not self.simulate and self.options.interactive):
                if not self.ask('Overwrite file %s?' % filename):
                    return
        if self.verbose > 1 and source:
            print 'Writing %s from %s' % (self.shorten(filename),
                                          self.shorten(source))
        elif self.verbose:
            print 'Writing %s' % self.shorten(filename)
        if not self.simulate:
            already_existed = os.path.exists(filename)
            if binary:
                f = open(filename, 'wb')
            else:
                f = open(filename, 'w')
            f.write(content)
            f.close()
            if (not already_existed
                and svn_add
                and os.path.exists(os.path.join(os.path.dirname(filename), '.svn'))):
                self.run_command('svn', 'add', filename)

    def parse_vars(self, args):
        result = {}
        for arg in args:
            if '=' not in arg:
                raise BadCommand(
                    'Variable assignment %r invalid (no "=")'
                    % arg)
            name, value = arg.split('=', 1)
            result[name] = value
        return result

class NotFoundCommand(Command):

    def run(self, args):
        #for name, value in os.environ.items():
        #    print '%s: %s' % (name, value)
        #print sys.argv
        print 'Command %s not known' % self.command_name
        commands = get_commands().items()
        commands.sort()
        print 'Known commands:'
        longest = max([len(n) for n, c in commands])
        for name, command in commands:
            print '  %s  %s' % (self.pad(name, length=longest),
                                command.load().summary)
        return 2
    
        
