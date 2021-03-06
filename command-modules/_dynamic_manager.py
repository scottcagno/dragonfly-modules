"""A command module for Dragonfly, for dynamically enabling/disabling
different grammars.

If a grammar is enabled that is conflicting with a previously enabled grammar,
the previously enabled grammar will be automatically disabled.
Each dynamic grammar module is responsible for keeping track of what other
modules it is incompatible with.

-----------------------------------------------------------------------------
Licensed under LGPL3

"""
import sys
import pkgutil

from dragonfly import (
    CompoundRule,
    MappingRule,
    RuleRef,
    Repetition,
    Function,
    IntegerRef,
    Dictation,
    Choice,
    Grammar
)

import lib.config
config = lib.config.get_config()

import lib.sound as sound
import dynamics

import os, glob

moduleMapping = {}


def notify_module_enabled(moduleName, useSound=True):
    """Notifies the user that a dynamic module has been enabled."""
    print("==> Dynamic grammar enabled: %s" % moduleName)
    if useSound:
        sound.play(sound.SND_ACTIVATE)


def notify_module_disabled(moduleName, useSound=True):
    """Notifies the user that a dynamic module has been disabled."""
    print("<-- Dynamic grammar disabled: %s" % moduleName)
    if useSound:
        sound.play(sound.SND_DEACTIVATE)


def notify_module_action_aborted(message, useSound=True):
    """Notifies the user, with a custom message, that the action was not
    completed.

    """
    print(message)
    if useSound:
        sound.play(sound.SND_MESSAGE)


def notify(message="", useSound=True):
    """Notifies the user, with a custom message, that the action was not
    completed.

    """
    if message:
        print(message)
    if useSound:
        sound.play(sound.SND_DING)


def enable_module(module, useSound=True):
    """Enables the specified module. Disables conflicting modules."""
    if not module:
        return
    moduleName = module.DYN_MODULE_NAME
    disable_incompatible_modules(module)
    status = module.dynamic_enable()
    if status:
        notify_module_enabled(moduleName, useSound)
        config = lib.config.get_config()
        config["dynamics.%s" % moduleName] = True
        lib.config.save_config()
    else:
        notify_module_action_aborted("Dynamic grammar %s already enabled." %
            moduleName)


def disable_module(module, useSound=True):
    """Disabled the specified module."""
    if not module:
        return
    status = module.dynamic_disable()
    moduleName = module.DYN_MODULE_NAME
    if status:
        notify_module_disabled(moduleName, useSound)
        config = lib.config.get_config()
        config["dynamics.%s" % moduleName] = False
        lib.config.save_config()


def disable_incompatible_modules(enableModule):
    """Iterates through the list of incompatible modules and disables them."""
    global moduleMapping
    for moduleName in enableModule.INCOMPATIBLE_MODULES:
        module = moduleMapping.get(moduleName)
        if module:
            disable_module(module, useSound=True)


def import_dynamic_modules():
    global moduleMapping
    config = lib.config.get_config()
    path = dynamics.__path__
    prefix = dynamics.__name__ + "."
    print("Loading dynamic grammar modules:")
    for importer, package_name, _ in pkgutil.iter_modules(path, prefix):
        print "---------- loading (not enabling): " + str(package_name)
        if package_name not in sys.modules:
            module = importer.find_module(package_name).load_module(
                package_name)
            moduleMapping[module.DYN_MODULE_NAME] = module
            enabled = config.get("dynamics.%s" % module.DYN_MODULE_NAME, False)
            print("    %s" % package_name + " : enabled: %s" % enabled)
            if enabled == True:
                enable_module(module, useSound=False)


import_dynamic_modules()


def disable_all_modules(useSound=True):
    """Iterates through the list of all dynamic modules and disables them."""
    global moduleMapping
    disableCount = 0
    config = lib.config.get_config()
    for moduleName, module in moduleMapping.items():
        status = module.dynamic_disable()
        if status:
            disableCount += 1
            config["dynamics.%s" % moduleName] = False
            notify_module_disabled(moduleName, useSound=False)
    if disableCount > 0:
        lib.config.save_config()
        if useSound:
            sound.play(sound.SND_DEACTIVATE)
        print("----------- All dynamic modules disabled -----------\n")
    else:
        print("---------- No dynamic modules are enabled ----------\n")


def show_module_status():
    """Iterates through the list of all dynamic modules and shows their
    status.

    """
    global moduleMapping
    config = lib.config.get_config()
    for moduleName, module in moduleMapping.items():
        if module.is_enabled():
            notify_module_enabled(moduleName, useSound=False)
        else:
            notify_module_disabled(moduleName, useSound=False)


def enable_modules(module, module2=None, module3=None, disableOthers=False):
    if disableOthers:
        disable_all_modules(useSound=False)
    modules = [module, module2, module3]
    incompatibleModules = []
    for module in modules:
        if module:
            if not module.DYN_MODULE_NAME in incompatibleModules:
                enable_module(module)
                incompatibleModules.extend(module.INCOMPATIBLE_MODULES)
            else:
                print("Grammar %s is incompatible with previous grammar" %
                    module.DYN_MODULE_NAME)


class SeriesMappingRule(CompoundRule):
    def __init__(self, mapping, extras=None, defaults=None):
        mapping_rule = MappingRule(mapping=mapping, extras=extras,
            defaults=defaults, exported=False)
        single = RuleRef(rule=mapping_rule)
        series = Repetition(single, min=1, max=16, name="series")

        compound_spec = "<series>"
        compound_extras = [series]
        CompoundRule.__init__(self, spec=compound_spec,
            extras=compound_extras, exported=True)

    def _process_recognition(self, node, extras):  # @UnusedVariable
        series = extras["series"]
        for action in series:
            action.execute()

series_rule = SeriesMappingRule(
    mapping={
        "enable <module> mode": Function(enable_modules),
        "enable <module> mode only": Function(enable_modules, disableOthers=True),  # @IgnorePep8
        "enable <module> and <module2> mode": Function(enable_modules),  # @IgnorePep8
        "enable <module> and <module2> mode only": Function(enable_modules, disableOthers=True),  # @IgnorePep8
        "enable <module> and <module2> and <module3> mode": Function(enable_modules),  # @IgnorePep8
        "enable <module> and <module2> and <module3> mode only": Function(enable_modules, disableOthers=True),  # @IgnorePep8
        "show dynamic [(mode|modes)] status": Function(show_module_status),
        "disable <module> mode": Function(disable_module),
        "disable [all] dynamic modes": Function(disable_all_modules),
    },
    extras=[
        IntegerRef("n", 1, 100),
        Dictation("text"),
        Choice("module", moduleMapping),
        Choice("module2", moduleMapping),
        Choice("module3", moduleMapping),
    ],
    defaults={
        "n": 1
    }
)


#---------------------------------------------------------------------------
# reload when one of dynamics/*.py is edited
class DynamicManagerGrammar(Grammar):

    def __init__(self):
        Grammar.__init__(self, name="Dynamic manager", context=None)

    def _process_begin(self, executable, title, handle):
    # Check for modified dynamic modules files, and if found cause reload dynamic manager module (_dynamic_manager.py) by config manager module (_dragonfly_tools.py) and the former causes reload of the dynamic module that has actually been edited
        dynamics_files = ["C:\Users\uc222343\Documents\GitHub\dragonfly-modules\command-modules\dynamics\%s" % x for x in glob.glob("C:\Users\uc222343\Documents\GitHub\dragonfly-modules\command-modules\dynamics\*_grammar.py")]
        
        for d in dynamics_files:
            #print d, __file__
            if not os.path.isfile(d):
                continue
            d_time = os.path.getmtime(d)
            module_time = os.path.getmtime(__file__)
            print d_time, module_time
            if d_time >= module_time:
                print "reloading %s to reload %s" % (os.path.basename(__file__), os.path.basename(d))
                os.utime(__file__, None) # set the access and modified times to the current time


#grammar = Grammar("Dynamic manager", context=None)
grammar = DynamicManagerGrammar()
grammar.add_rule(series_rule)
grammar.load()


notify()  # Notify that Dragonfly is ready with a sound.


def unload():
    """Unload function which will be called at unload time."""
    # Unload the dynamically loaded modules.
    global moduleMapping
    for module in moduleMapping.values():
        print "---------- " + __file__.split('\\')[-1] + " unload(): " + str(module.__name__)
        module.unload()

    global grammar
    if grammar:
        grammar.unload()
    grammar = None

#---------------------------------------------------------------------------
# Set up this module's configuration. In this module's particular case, this doesn't necessarily make alot of sense, as this file/module is not expected to be edited every day, and it doesn't have/need a config file ie .txt, but having this make it easier to bring this module into notepad via _dragonfly_tools.py/config manager "edit dynamic manager module" command
# may be should combine dynamics/*.py into one _dragonfly_tools.txt config file, so that on editing the config file the the main .py module gets touced (via a method in _dragonfly_tools.py) and cause it to reload (even thought this reload is not reliable and sometimes needs sleep/wakeup or microphoneOff/microphoneOn to properly reload the newly edited moudle and it's config)
# alternatively re-employ the method/function of _dragonfly_tools.py that touches the .py when .txt is edited, to make it re-touch _dynamic_manager.py when any of dynamics/*.py is edited

from dragonfly import Config
dragonfly_config = Config("dynamic manager") # config is already used for lib/config.py's config.json file
dragonfly_config.load()
