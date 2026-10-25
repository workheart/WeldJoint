import adsk.core
import adsk.fusion
from dataclasses import dataclass, field
import itertools
import json
import math
import os
import re

from .fusion_brep_util import *
from .fusion_base_combines import BaseCombines
from .fusion_cf_addin import FusionCustomFeatureAddIn
from .fusion_util import *


@dataclass
class WeldJointParameters:
	"""
	All parameters that define a specific weld joint.

	Note that assignment of default values is deferred to instance creation time
	(using `default_factory`) rather than using static values because `Parameter` units
	will vary within the context of the current document and user preferences.
	"""
	faces: list[EntityRef] = field(default_factory=list)
	mode: str = 'fingers'  # One of `_modeNames`.
	tabPoints: list[EntityRef] = field(default_factory=list)
	minFingers: Parameter = field(
		default_factory=lambda: Parameter(3))
	maxFingers: Parameter = field(
		default_factory=lambda: Parameter(33))
	minFingerWidth: Parameter = field(
		default_factory=lambda: Parameter.length(centimeters=cmOrIn(2.5, 1)))  # 2.5cm or 1"
	maxFingerWidth: Parameter = field(
		default_factory=lambda: Parameter.length(centimeters=cmOrIn(15, 6)))  # 15cm or 6"
	fingerRatio: Parameter = field(
		default_factory=lambda: Parameter(0.5))
	tabWidth: Parameter = field(
		default_factory=lambda: Parameter.length(centimeters=cmOrIn(2, 0.75)))  # 2cm or 3/4"
	tabSpacing: Parameter = field(
		default_factory=lambda: Parameter.length(centimeters=cmOrIn(10, 4)))  # 10cm or 4"
	margin: Parameter = field(
		default_factory=lambda: Parameter.length(centimeters=0))
	tabSetback: Parameter = field(
		default_factory=lambda: Parameter.length(centimeters=0))
	slotClearance: Parameter = field(
		default_factory=lambda: Parameter.length(centimeters=0))
	holeClearance: Parameter = field(
		default_factory=lambda: Parameter.length(centimeters=0))


# All custom feature parameters (ids match the dialog inputs and `WeldJointParameters` fields).
_parameterDescriptions = {
	'minFingers': 'Min Fingers',
	'maxFingers': 'Max Fingers',
	'minFingerWidth': 'Min Finger Width',
	'maxFingerWidth': 'Max Finger Width',
	'fingerRatio': 'Finger Ratio',
	'tabWidth': 'Tab Width',
	'tabSpacing': 'Tab Spacing',
	'margin': 'Corner Margin',
	'tabSetback': 'Tab Setback',
	'slotClearance': 'Slot Clearance',
	'holeClearance': 'Hole Clearance',
}

# Joint modes: id -> name in the dialog.
_modeNames = {
	'fingers': 'Fingers',
	'tabs': 'Tabs: Spacing',
	'points': 'Tabs: Points',
}

# Inputs only shown in some modes (all other inputs are always shown).
_modeInputIds = {
	'fingers': ('minFingers', 'maxFingers', 'minFingerWidth', 'maxFingerWidth', 'fingerRatio', 'margin'),
	'tabs': ('tabWidth', 'tabSpacing', 'margin'),
	'points': ('tabPoints', 'tabWidth'),
}

# Tooltips per input: (always shown, shown when hovering longer).
# A tool clip image is shown as well if `_toolClipFolder/<input id>.png` exists.
_tooltips = {
	'faces': ('Outside faces of the plates to join.',
		'Select the outside face of each plate. A joint is made wherever a selected plate '
		'butts against another selected plate, at any angle.'),
	'mode': ('How the joint is built.',
		'<b>Fingers</b>: alternating fingers along the whole edge.<br>'
		'<b>Tabs: Spacing</b>: tabs of a fixed width, spread evenly.<br>'
		'<b>Tabs: Points</b>: one tab at each selected sketch point.'),
	'tabPoints': ('Sketch points that place the tabs.',
		'Each point places one tab, centered along the edge. Draw the points in a sketch on an '
		'outside face, on the edge or anywhere within the plate thickness. Dimension them in the '
		'sketch: the tabs follow when the sketch changes.'),
	'minFingers': ('Smallest number of fingers (odd).',
		'Counts the fingers of both plates together. '
		'If an edge is too short for this number, it gets no joint.'),
	'maxFingers': ('Largest number of fingers (odd).',
		'Counts the fingers of both plates together.'),
	'minFingerWidth': ('Smallest finger width.',
		'The joint uses as many fingers as fit with at least this width.'),
	'maxFingerWidth': ('Largest finger width.',
		'If the fingers would get wider, the extra length goes to the corners.'),
	'fingerRatio': ('Width share of the fingers on the butting plate.',
		'0.5 makes all fingers equally wide. Smaller values make the fingers of the butting plate '
		'narrower, like tabs.'),
	'tabWidth': ('Width of each tab along the edge.', None),
	'tabSpacing': ('Largest gap between two tabs.',
		'The tabs are spread evenly. All gaps, also those to the ends of the edge, are equal '
		'and never larger than this value.'),
	'margin': ('Extra distance from the corners.',
		'Moves all fingers or tabs inward by this distance, from both ends of the edge.'),
	'tabSetback': ('Makes the tabs shorter.',
		'The tabs end this far below the outside face of the other plate, '
		'which leaves room for the weld.'),
	'slotClearance': ('Play along the edge, per side.',
		'Each slot is longer than its tab by this value, on both sides.'),
	'holeClearance': ('Play across the edge, per side.',
		'Each slot is wider than the plate thickness by this value, on both sides. '
		'Only for closed holes inside a face, not for notches at a corner.'),
}

_toolClipFolder = os.path.join(os.path.dirname(__file__), 'Resources', 'ToolClips')

# Last used settings (mode and parameter expressions), shared by all documents.
_settingsPath = os.path.join(os.path.dirname(__file__), 'last_settings.json')


class WeldJointAddIn(FusionCustomFeatureAddIn):
	"""
	The Weld Joint Fusion Add-In (based on Box Joint by Mark Suska).
	"""
	def __init__(self):
		super().__init__(
			baseCommandId='Kabelfrikkler_WeldJoint',
			name='Weld Joint',
			createTooltip='Create weld tabs or finger joints between two or more plates.',
			editTooltip='Edit weld tabs or finger joints between plates.',
			resourceFolder='Resources/WeldJoint',
			toolClipFilename=os.path.join(_toolClipFolder, 'command.png'),
			toolbarControls=[
				{
					'workspace': 'FusionSolidEnvironment',
					'panel': 'SolidScriptsAddinsPanel',
				},
				{
					'workspace': 'FusionSolidEnvironment',
					'panel': 'SolidModifyPanel',
					'afterControl': 'FusionCombineCommand',
					'promote': True
				},
			],
		)

	def createInputs(self, command: adsk.core.Command, params: WeldJointParameters):
		inputs = command.commandInputs

		# Create the selection input to select the planar faces on solid bodies.
		# Note: Selections cannot be pre-populated now.
		facesSelectInput = inputs.addSelectionInput(
			'faces',
			'Faces',
			'Select outside faces of bodies to join.')
		facesSelectInput.addSelectionFilter('SolidFaces')
		facesSelectInput.setSelectionLimits(2)  # At least two faces needed.

		input = inputs.addDropDownCommandInput(
			'mode', 'Mode', adsk.core.DropDownStyles.TextListDropDownStyle)
		for mode, name in _modeNames.items():
			input.listItems.add(name, mode == params.mode)

		pointsSelectInput = inputs.addSelectionInput(
			'tabPoints',
			'Tab Points',
			'Select sketch points on the joints to place tabs at.')
		pointsSelectInput.addSelectionFilter('SketchPoints')
		pointsSelectInput.addSelectionFilter('ConstructionPoints')
		pointsSelectInput.setSelectionLimits(0)  # Checked in `areInputsValid` (only in points mode).

		input = inputs.addIntegerSpinnerCommandInput(
			'minFingers', 'Min Fingers',
			min=3, max=99, spinStep=2,
			initialValue=int(clamp(params.minFingers.value, 3, 99)))
		input.expression = params.minFingers.expression

		input = inputs.addIntegerSpinnerCommandInput(
			'maxFingers', 'Max Fingers',
			min=3, max=99, spinStep=2,
			initialValue=int(clamp(params.maxFingers.value, 3, 99)))
		input.expression = params.maxFingers.expression

		addLengthInput(inputs, 'minFingerWidth', 'Min Finger Width', params.minFingerWidth)
		addLengthInput(inputs, 'maxFingerWidth', 'Max Finger Width', params.maxFingerWidth)

		input = inputs.addFloatSpinnerCommandInput(
			'fingerRatio', 'Finger Ratio',
			unitType=Parameter.UNITLESS, min=0.01, max=0.99, spinStep=0.1,
			initialValue=clamp(params.fingerRatio.value, 0.01, 0.99))
		input.expression = params.fingerRatio.expression

		addLengthInput(inputs, 'tabWidth', 'Tab Width', params.tabWidth)
		addLengthInput(inputs, 'tabSpacing', 'Tab Spacing', params.tabSpacing)

		addLengthInput(inputs, 'margin', 'Corner Margin', params.margin, isZeroAllowed=True)
		addLengthInput(inputs, 'tabSetback', 'Tab Setback', params.tabSetback, isZeroAllowed=True)
		addLengthInput(inputs, 'slotClearance', 'Slot Clearance', params.slotClearance, isZeroAllowed=True)
		addLengthInput(inputs, 'holeClearance', 'Hole Clearance', params.holeClearance, isZeroAllowed=True)

		# For error message output.
		inputs.addTextBoxCommandInput('error', '', '', numRows=1, isReadOnly=True)

		for inputId, (tooltip, description) in _tooltips.items():
			setTooltip(inputs.itemById(inputId), tooltip, description)

		updateInputVisibility(inputs)

	def canSelect(self, entity, input: adsk.core.SelectionCommandInput) -> bool:
		if input.id == 'faces':
			# Must be a planar face on a solid body.
			if entity.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
				return False
			if not entity.body.isSolid:
				return False
		return True

	def inputChanged(self, input: adsk.core.CommandInput, commandInputs: adsk.core.CommandInputs):
		if input.id == 'mode':
			updateInputVisibility(commandInputs)

	def areInputsValid(self, commandInputs: adsk.core.CommandInputs) -> bool:
		errorMessage = None
		try:
			for input in commandInputs:
				if input.isVisible and hasattr(input, 'isValidExpression') and not input.isValidExpression:
					raise UserInputError(input, 'is invalid')

			mode = selectedMode(commandInputs)
			if mode == 'fingers':
				for inputId in 'minFingers', 'maxFingers':
					input = commandInputs.itemById(inputId)
					value = input.value
					if math.floor(value) != math.ceil(value):
						raise UserInputError(input, 'must be an integer')
					if int(value) & 1 == 0:
						raise UserInputError(input, 'must be odd')
			if mode == 'points':
				input = commandInputs.itemById('tabPoints')
				if input.selectionCount == 0:
					raise UserInputError(input, 'needs at least one point')
		except UserInputError as error:
			errorMessage = f'<span style="color:red"><b>{error.input.name}</b> {error.message}.</span>'

		# Set error message only if it has changed.
		errorBox: adsk.core.TextBoxCommandInput = commandInputs.itemById('error')
		if errorMessage:
			if errorBox.text != withoutHtml(errorMessage):
				log(f'User input error: {withoutHtml(errorMessage)}')
				errorBox.formattedText = errorMessage
		elif errorBox.text:
			log(f'User input error cleared')
			errorBox.formattedText = ''

		return errorMessage is None

	def defaultParams(self) -> WeldJointParameters:
		return loadSettings(WeldJointParameters())

	def commandCompleted(self, params: WeldJointParameters):
		saveSettings(params)

	def paramsToInputs(self, params: WeldJointParameters, commandInputs: adsk.core.CommandInputs):
		facesInput: adsk.core.SelectionCommandInput = commandInputs.itemById('faces')
		facesInput.clearSelection()
		for face in params.faces:
			facesInput.addSelection(face.entity)

		for item in commandInputs.itemById('mode').listItems:
			item.isSelected = item.name == _modeNames[params.mode]
		for parameterId, parameter in self.getCustomParameters(params).items():
			commandInputs.itemById(parameterId).expression = parameter.expression

		# Show the points input before selecting points, since hiding it clears its selections.
		updateInputVisibility(commandInputs)
		pointsInput: adsk.core.SelectionCommandInput = commandInputs.itemById('tabPoints')
		pointsInput.clearSelection()
		for point in params.tabPoints:
			if point.entity:
				pointsInput.addSelection(point.entity)

	def inputsToParams(self, commandInputs: adsk.core.CommandInputs) -> WeldJointParameters:
		facesInput: adsk.core.SelectionCommandInput = commandInputs.itemById('faces')
		faces = []
		for i in range(0, facesInput.selectionCount):
			faces.append(EntityRef(facesInput.selection(i).entity))

		pointsInput: adsk.core.SelectionCommandInput = commandInputs.itemById('tabPoints')
		tabPoints = []
		for i in range(0, pointsInput.selectionCount):
			tabPoints.append(EntityRef(pointsInput.selection(i).entity))

		return WeldJointParameters(
			faces=faces,
			mode=selectedMode(commandInputs),
			tabPoints=tabPoints,
			**{parameterId: Parameter(commandInputs.itemById(parameterId))
				for parameterId in _parameterDescriptions})

	def customFeatureToParams(self, feature: adsk.fusion.CustomFeature) -> WeldJointParameters:
		customNamedValues = feature.customNamedValues
		# Built-in defaults rather than the last used settings, so that recomputing
		# an older feature does not depend on what was used last.
		defaults = WeldJointParameters()

		faces = [EntityRef(token) for token in
			customNamedValues.value('faces').split()]

		if customNamedValues.isExistingValue('mode'):
			mode = customNamedValues.value('mode')
		elif (customNamedValues.isExistingValue('tabMode')
			and customNamedValues.value('tabMode') == 'true'):
			# Feature created when there was only a "Fixed Tabs" check box.
			mode = 'tabs'
		else:
			mode = 'fingers'

		tabPoints = []
		if customNamedValues.isExistingValue('tabPoints'):
			tabPoints = [EntityRef(token) for token in
				customNamedValues.value('tabPoints').split()]

		return WeldJointParameters(
			faces=faces,
			mode=mode,
			tabPoints=tabPoints,
			**{parameterId: featureParameter(feature, parameterId, getattr(defaults, parameterId))
				for parameterId in _parameterDescriptions})

	def getCustomParameters(self, params: WeldJointParameters) -> dict[str, Parameter]:
		return {parameterId: getattr(params, parameterId) for parameterId in _parameterDescriptions}

	def getCustomParameterDescriptions(self) -> dict[str, str]:
		return _parameterDescriptions

	def getCustomNamedValues(self, params: WeldJointParameters) -> dict[str, str]:
		return {
			'faces': ' '.join([face.entityToken for face in params.faces]),
			'mode': params.mode,
			'tabPoints': ' '.join([point.entityToken for point in params.tabPoints]),
		}

	def getDependencies(self, params: WeldJointParameters) -> dict[str, adsk.core.Base]:
		bodies = {}
		for face in params.faces:
			body = face.entity.body
			bodies[body.revisionId] = body
		dependencies = {f'body{i}': body for i, body in enumerate(bodies.values())}

		# Moving a tab point (e.g. by changing a sketch dimension) recomputes the joint.
		points = [point.entity for point in params.tabPoints if point.entity]
		dependencies.update({f'point{i}': point for i, point in enumerate(points)})
		return dependencies

	def createOrUpdateChildFeatures(self,
		params: WeldJointParameters,
		existingFeatures: list[adsk.fusion.Feature],
		allowFeatureCreationAndDeletion: bool
	) -> list[adsk.fusion.Feature]:
		baseCombines = computeWeldJoint(params)
		features = baseCombines.createOrUpdate(
			existingFeatures=existingFeatures,
			allowFeatureCreationAndDeletion=allowFeatureCreationAndDeletion)
		return features


def addLengthInput(
	inputs: adsk.core.CommandInputs,
	inputId: str,
	name: str,
	param: Parameter,
	isZeroAllowed: bool = False
) -> adsk.core.ValueCommandInput:
	"""
	Add a value input for a length that must be positive (or non-negative if `isZeroAllowed`).
	"""
	input = inputs.addValueInput(
		inputId, name,
		unitType=param.units,
		initialValue=param.valueInput)
	input.minimumValue = 0
	input.isMinimumInclusive = isZeroAllowed
	input.isMinimumLimited = True
	return input


def setTooltip(input: adsk.core.CommandInput, tooltip: str, description: str = None):
	"""
	Set the tooltip of the given `input`, plus its tool clip image if there is one.
	"""
	input.tooltip = tooltip
	if description:
		input.tooltipDescription = description
	toolClipFilename = os.path.join(_toolClipFolder, f'{input.id}.png')
	if os.path.isfile(toolClipFilename):
		input.toolClipFilename = toolClipFilename


def loadSettings(params: WeldJointParameters) -> WeldJointParameters:
	"""
	Apply the last used settings to the given `params`. Values that are not valid in the
	active document (e.g. expressions using user parameters of another document) are skipped.
	"""
	try:
		with open(_settingsPath, encoding='utf-8') as file:
			settings = json.load(file)
		if settings.get('mode') in _modeNames:
			params.mode = settings['mode']
		unitsManager = adsk.core.Application.get().activeProduct.unitsManager
		for parameterId, (expression, units) in settings.get('parameters', {}).items():
			if parameterId in _parameterDescriptions and unitsManager.isValidExpression(expression, units):
				setattr(params, parameterId, Parameter(expression, units))
	except FileNotFoundError:
		pass
	except Exception:
		handleException()
	return params


def saveSettings(params: WeldJointParameters):
	"""
	Remember the mode and parameter values of the given `params` (not the selections).
	"""
	settings = {
		'mode': params.mode,
		'parameters': {parameterId: [getattr(params, parameterId).expression, getattr(params, parameterId).units]
			for parameterId in _parameterDescriptions},
	}
	try:
		with open(_settingsPath, 'w', encoding='utf-8') as file:
			json.dump(settings, file, indent='\t')
	except Exception:
		handleException()


def selectedMode(commandInputs: adsk.core.CommandInputs) -> str:
	"""
	The id of the mode selected in the dialog.
	"""
	name = commandInputs.itemById('mode').selectedItem.name
	return next(mode for mode, modeName in _modeNames.items() if modeName == name)


def updateInputVisibility(commandInputs: adsk.core.CommandInputs):
	"""
	Show only the inputs used by the selected mode.
	"""
	visibleInputIds = _modeInputIds[selectedMode(commandInputs)]
	for inputId in set(itertools.chain(*_modeInputIds.values())):
		commandInputs.itemById(inputId).isVisible = inputId in visibleInputIds


def featureParameter(feature: adsk.fusion.CustomFeature, parameterId: str, default: Parameter) -> Parameter:
	"""
	Read a parameter of the given custom `feature`.

	Features created by an older version of this Add-In lack newer parameters, and parameters
	cannot be added to an existing custom feature. Their values are kept as custom named values
	instead (see `FusionCustomFeatureAddIn._updateCustomFeature`), or the `default` is used.
	"""
	parameter = feature.parameters.itemById(parameterId)
	if parameter:
		return Parameter(parameter)
	if feature.customNamedValues.isExistingValue(parameterId):
		return Parameter(feature.customNamedValues.value(parameterId), default.units)
	return default


def computeWeldJoint(params: WeldJointParameters) -> BaseCombines:
	baseCombines = BaseCombines()

	if len(params.faces) < 2:
		return baseCombines

	# Normalize parameter values.
	faces = [face.entity for face in params.faces]
	mode = params.mode
	tabPoints = [pointGeometry(point.entity) for point in params.tabPoints if point.entity]
	minFingers = max(int(params.minFingers.value), 3) | 1
	maxFingers = max(int(params.maxFingers.value) - 1, minFingers) | 1
	minFingerWidth = max(params.minFingerWidth.value, 0.0001)
	maxFingerWidth = max(params.maxFingerWidth.value, minFingerWidth)
	fingerRatio = clamp(params.fingerRatio.value,
		minFingerWidth / (minFingerWidth + maxFingerWidth),
		maxFingerWidth / (minFingerWidth + maxFingerWidth))
	rAB = (1 - fingerRatio) / fingerRatio
	rBA = fingerRatio / (1 - fingerRatio)
	tabWidth = max(params.tabWidth.value, 0.0001)
	tabSpacing = max(params.tabSpacing.value, 0.0001)
	margin = max(params.margin.value, 0)
	tabSetback = max(params.tabSetback.value, 0)
	slotClearance = max(params.slotClearance.value, 0)
	holeClearance = max(params.holeClearance.value, 0)

	# Add all possible target bodies in case there are no operations on some.
	for face in faces:
		baseCombines.addTargetBody(face.body)

	# Compute the box joint between each pair of faces.
	for faceA, faceB, buttingFace in getAllButtingFaces(faces):
		bodyA = faceA.body
		bodyB = faceB.body
		planeA: adsk.core.Plane = faceA.geometry
		planeB: adsk.core.Plane = faceB.geometry
		faceAInwardNormal = planeA.normal.copy()
		faceBInwardNormal = planeB.normal.copy()

		# Normalize the orientation of the joint.
		if not faceA.isParamReversed:
			faceAInwardNormal.scaleBy(-1)
			planeA.normal = faceAInwardNormal
		if not faceB.isParamReversed:
			faceBInwardNormal.scaleBy(-1)
			planeB.normal = faceBInwardNormal

		# Define actual Joint and Nominal coordinate systems.
		# Nominal: Z along the joint, Y through body A (from its outside face),
		# X across body B.
		outerEdge = planeB.intersectWithPlane(planeA)
		jointOrigin = outerEdge.origin
		jointZAxis = outerEdge.direction
		jointYAxis = faceAInwardNormal
		jointXAxis = faceAInwardNormal.crossProduct(jointZAxis)
		jointToNominal = adsk.core.Matrix3D.create()
		jointToNominal.setToAlignCoordinateSystems(
			fromOrigin=jointOrigin,
			fromXAxis=jointXAxis,
			fromYAxis=jointYAxis,
			fromZAxis=jointZAxis,
			toOrigin=adsk.core.Point3D.create(0, 0, 0),
			toXAxis=adsk.core.Vector3D.create(1, 0, 0),
			toYAxis=adsk.core.Vector3D.create(0, 1, 0),
			toZAxis=adsk.core.Vector3D.create(0, 0, 1))
		nominalToJoint = jointToNominal.copy()
		nominalToJoint.invert()

		# Sweep the butting face to define the overlapping region between
		# body A and body B where the joint will be created.
		sweepLine = adsk.core.InfiniteLine3D.create(
			jointOrigin, faceBInwardNormal.crossProduct(jointZAxis))
		pB: adsk.core.Point3D = buttingFace.geometry.intersectWithLine(sweepLine)
		sweepVector = pB.vectorTo(jointOrigin)
		overlap = createObliquePrism(buttingFace, sweepVector)
		tempBrepMgr.booleanOperation(overlap, bodyA, adsk.fusion.BooleanTypes.IntersectionBooleanType)
		tempBrepMgr.transform(overlap, jointToNominal)
		overlapBox = overlap.boundingBox
		minX, minY, minZ = overlapBox.minPoint.asArray()
		maxX, maxY, maxZ = overlapBox.maxPoint.asArray()

		# Compute the positions and widths of the fingers on body B (the tabs) as offsets
		# from minZ. Fingers alternate between body A and body B (A, B, A, ..., B, A).
		lengthWithMargins = maxZ - minZ
		length = lengthWithMargins - 2 * margin
		if mode == 'points':
			# One tab centered on each point that lies on this joint (within one material thickness).
			fingerBWidth = tabWidth
			tolerance = max(maxX - minX, maxY - minY)
			tabOffsets = []
			for point in tabPoints:
				p = point.copy()
				p.transformBy(jointToNominal)
				if (minX - tolerance <= p.x <= maxX + tolerance
					and minY - tolerance <= p.y <= maxY + tolerance
					and minZ <= p.z <= maxZ):
					tabOffsets.append(p.z - minZ - tabWidth / 2)
			if not tabOffsets:
				# No points on this joint.
				continue
		elif mode == 'tabs':
			# Tabs have a fixed width and are evenly distributed
			# with gaps no larger than the tab spacing.
			if length <= tabWidth:
				# Too short for a single tab.
				continue
			tabs = max(math.ceil((length - tabSpacing) / (tabWidth + tabSpacing)), 1)
			fingers = 2 * tabs + 1
			fingerBWidth = tabWidth
			fingerAWidth = (length - tabs * tabWidth) / (tabs + 1)
		else:
			if fingerRatio < 0.5:
				fingerAWidth = min(minFingerWidth * rAB, maxFingerWidth)
			else:
				fingerAWidth = minFingerWidth
			fingers = min(
				math.floor(2 * (length / fingerAWidth - 1) / (1 + rBA)) | 1,
				maxFingers)
			if fingers < minFingers:
				# Would have too few fingers.
				continue
			fingerAWidth = length / ((1 + rBA) * math.floor(fingers / 2) + 1)
			if fingerAWidth > maxFingerWidth:
				fingerAWidth = maxFingerWidth
			fingerBWidth = fingerAWidth * rBA
			if fingerBWidth > maxFingerWidth:
				fingerBWidth = maxFingerWidth
				fingerAWidth = maxFingerWidth * rAB
		if mode != 'points':
			length = fingerAWidth + math.floor(fingers / 2) * (fingerAWidth + fingerBWidth)
			endMargin = (lengthWithMargins - length) / 2
			tabOffsets = [endMargin + fingerAWidth + i * (fingerAWidth + fingerBWidth)
				for i in range(0, math.floor(fingers / 2))]

		# Create a transformation matrix that will be reused for all upward translations.
		translateUp = adsk.core.Matrix3D.create()

		# Create a template for a single B finger.
		finger = createSimpleBox(
			minX, minY, minZ,
			maxX - minX, maxY - minY, fingerBWidth)

		# Define various reference points and vectors on the finger cross-section.
		pO = jointOrigin.copy()
		pO.transformBy(jointToNominal)
		pO.z = minZ
		pB.transformBy(jointToNominal)
		pB.z = minZ
		vOB = pO.vectorTo(pB)
		vOBPerp = adsk.core.Vector3D.create(vOB.y, -vOB.x, 0)

		isObtuse = pB.x < pO.x - adsk.core.Application.get().pointTolerance

		if isObtuse:
			# Joint angle is > 90°.
			pI = adsk.core.Point3D.create(maxX + vOB.x, maxY, minZ)
			pA = adsk.core.Point3D.create(maxX, minY, minZ)
			pAe = adsk.core.Point3D.create(max(pI.x, pO.x), minY, minZ)
			lOB = adsk.core.InfiniteLine3D.create(pO, vOB)
			lBeI = adsk.core.InfiniteLine3D.create(pI, vOBPerp)
			pBe = lOB.intersectWithCurve(lBeI)[0]
			if pBe.y < minY:
				pBe = pO
			vOBe = pO.vectorTo(pBe)
			pBe = pO.copy()
			pBe.translateBy(vOBe)

			# Slope the finger.
			try:
				slopeCrossSection = createFaceFromCurves([
					adsk.core.Line3D.create(pI, pAe),
					adsk.core.Line3D.create(pAe, pA),
					adsk.core.Line3D.create(pA, pI),
				])
				slope = createPrism(slopeCrossSection, fingerBWidth)
				tempBrepMgr.booleanOperation(finger, slope, adsk.fusion.BooleanTypes.DifferenceBooleanType)
			except RuntimeError as e:
				# Ignore if slope is too tiny.
				if not any('ASM_WIRE_SELF_INTERSECTS' in arg for arg in e.args):
					raise
			try:
				# This slope runs along the whole joint (each finger covers it, clipped by the overlap).
				slopeCrossSection = createFaceFromCurves([
					adsk.core.Line3D.create(pI, pB),
					adsk.core.Line3D.create(pB, pBe),
					adsk.core.Line3D.create(pBe, pI),
				])
				slope = createPrism(slopeCrossSection, -lengthWithMargins)
				tempBrepMgr.booleanOperation(finger, slope, adsk.fusion.BooleanTypes.UnionBooleanType)
				slope = createPrism(slopeCrossSection, fingerBWidth + lengthWithMargins)
				tempBrepMgr.booleanOperation(finger, slope, adsk.fusion.BooleanTypes.UnionBooleanType)
			except RuntimeError as e:
				# Ignore if slope is too tiny.
				if not any('ASM_WIRE_SELF_INTERSECTS' in arg for arg in e.args):
					raise

		# The cutter for body A: the slot is longer than the tab by the slot clearance on each side,
		# and wider by the hole clearance on each side where the slot is a closed hole in a face.
		fingerACutter = createWidenedBody(
			finger, adsk.core.Vector3D.create(0, 0, 1), slotClearance, fingerBWidth)
		cutterRegion = overlap
		if holeClearance > 0 and isClosedHole(overlap, bodyA, nominalToJoint, holeClearance):
			xAxis = adsk.core.Vector3D.create(1, 0, 0)
			maxStep = (maxX - minX) / 4
			fingerACutter = createWidenedBody(fingerACutter, xAxis, holeClearance, maxStep)
			cutterRegion = createWidenedBody(overlap, xAxis, holeClearance, maxStep)

		# The joiner for body B (the tab), shortened by the tab setback so that it ends
		# below the outside face of body A.
		fingerBJoiner = finger
		hasTabs = tabSetback < maxY - minY
		if tabSetback > 0 and hasTabs:
			fingerBox = finger.boundingBox
			setback = createSimpleBox(
				fingerBox.minPoint.x - 1, fingerBox.minPoint.y - 1, minZ,
				fingerBox.maxPoint.x - fingerBox.minPoint.x + 2,
				minY + tabSetback - fingerBox.minPoint.y + 1,
				fingerBWidth)
			tempBrepMgr.booleanOperation(fingerBJoiner, setback, adsk.fusion.BooleanTypes.DifferenceBooleanType)

		# Move each finger into its final position and combine with body A and body B.
		for tabOffset in tabOffsets:
			translateUp.setCell(2, 3, tabOffset)

			finger = tempBrepMgr.copy(fingerACutter)
			tempBrepMgr.transform(finger, translateUp)
			tempBrepMgr.booleanOperation(finger, cutterRegion, adsk.fusion.BooleanTypes.IntersectionBooleanType)
			tempBrepMgr.transform(finger, nominalToJoint)
			baseCombines.add(BooleanOperation.difference(
				targetBody=bodyA,
				toolBody=finger))

			if hasTabs:
				finger = tempBrepMgr.copy(fingerBJoiner)
				tempBrepMgr.transform(finger, translateUp)
				tempBrepMgr.booleanOperation(finger, overlap, adsk.fusion.BooleanTypes.IntersectionBooleanType)
				tempBrepMgr.transform(finger, nominalToJoint)
				baseCombines.add(BooleanOperation.union(
					targetBody=bodyB,
					toolBody=finger))

	return baseCombines


def pointGeometry(point) -> adsk.core.Point3D:
	"""
	The position of a sketch point or construction point in world coordinates.
	"""
	if isinstance(point, adsk.fusion.SketchPoint):
		return point.worldGeometry
	return point.geometry


def isClosedHole(
	overlap: adsk.fusion.BRepBody,
	body: adsk.fusion.BRepBody,
	nominalToJoint: adsk.core.Matrix3D,
	distance: float
) -> bool:
	"""
	Check whether the given `body` continues on both sides of the joint region `overlap`
	(in nominal coordinates) across the joint, for at least `distance`.
	If so, a slot cut there is a closed hole inside a face rather than a notch at an edge.
	"""
	for sign in 1, -1:
		translation = adsk.core.Matrix3D.create()
		translation.translation = adsk.core.Vector3D.create(sign * distance, 0, 0)
		side = tempBrepMgr.copy(overlap)
		tempBrepMgr.transform(side, translation)
		tempBrepMgr.booleanOperation(side, overlap, adsk.fusion.BooleanTypes.DifferenceBooleanType)
		sideVolume = side.volume
		tempBrepMgr.transform(side, nominalToJoint)
		tempBrepMgr.booleanOperation(side, body, adsk.fusion.BooleanTypes.IntersectionBooleanType)
		if side.volume < 0.5 * sideVolume:
			return False
	return True


def getAllButtingFaces(outsideFaces: list[adsk.fusion.BRepFace]) -> list[tuple[
	adsk.fusion.BRepFace, adsk.fusion.BRepFace, adsk.fusion.BRepFace
]]:
	buttingFaces = []
	for faceA, faceB in itertools.permutations(outsideFaces, 2):
		for buttingFace in getButtingFaces(faceA, faceB):
			buttingFaces.append((faceA, faceB, buttingFace))
	return buttingFaces


def getButtingFaces(faceA: adsk.fusion.BRepFace, faceB: adsk.fusion.BRepFace) -> list[adsk.fusion.BRepFace]:
	buttingFaces = []

	if faceA.body == faceB.body:
		# Both faces on same body.
		return buttingFaces
	if faceA.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
		# Face A is not planar.
		return buttingFaces
	if faceB.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
		# Face B is not planar.
		return buttingFaces

	# Check all planar faces adjacent to face B.
	for edgeOnFaceB in faceB.edges:
		for candidateButtingFace in edgeOnFaceB.faces:
			if candidateButtingFace == faceB:
				# This is face B itself, not an adjacent face.
				continue
			candidateButtingFaceGeometry = candidateButtingFace.geometry
			if candidateButtingFaceGeometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
				# Not a planar face.
				continue
			if not candidateButtingFaceGeometry.isParallelToPlane(faceA.geometry):
				# Not parallel to face A.
				continue
			if candidateButtingFaceGeometry.isCoPlanarTo(faceA.geometry):
				# There is zero distance to face A.
				continue

			# Check that there is an overlapping exterior face on body A.
			for f in faceA.body.shells[0].faces:
				if f.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
					continue
				if not candidateButtingFaceGeometry.isCoPlanarTo(f.geometry):
					continue
				imprint = tempBrepMgr.imprintOverlapBodies(
					tempBrepMgr.copy(candidateButtingFace),
					tempBrepMgr.copy(f),
					False)
				if imprint[3].size() > 0:
					# This face butts up with a face on body A.
					buttingFaces.append(candidateButtingFace)

	return buttingFaces


def clamp(value, min, max):
	"""
	Clamps the given `value` to be between the given `min` and `max` values.
	"""
	return min if value < min else max if value > max else value


_htmlTagRegex = re.compile('<[^>]*>')
def withoutHtml(string):
	"""
	Removes all HTML tags from the given `string`.
	"""
	return re.sub(_htmlTagRegex, '', string)
