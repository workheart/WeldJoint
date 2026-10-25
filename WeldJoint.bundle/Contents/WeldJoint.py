import importlib

from . import fusion_util, fusion_brep_util, fusion_base_combines, fusion_cf_addin, fusion_weld_joint
from .fusion_util import log, handleException


log(f'Loading Fusion Add-In {repr(__file__)} ...')


# All modules of this Add-In, in dependency order.
_modules = [fusion_util, fusion_brep_util, fusion_base_combines, fusion_cf_addin, fusion_weld_joint]

thisAddIn: fusion_weld_joint.WeldJointAddIn = None


def run(context):
	try:
		log(f'Starting Fusion Add-In {repr(__file__)} ...')

		# Fusion keeps imported modules cached when an Add-In is stopped and started again,
		# so reload them to pick up code changes.
		for module in _modules:
			importlib.reload(module)

		global thisAddIn
		thisAddIn = fusion_weld_joint.WeldJointAddIn()
	except:
		handleException()


def stop(context):
	try:
		log(f'Stopping Fusion Add-In {repr(__file__)} ...')
		global thisAddIn
		if thisAddIn:
			thisAddIn.destroy()
		thisAddIn = None
	except:
		handleException()


log(f'Finished loading Fusion Add-In {repr(__file__)}')
