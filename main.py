import json
import subprocess
import os
import sys
import platform
import shutil
import re
import importlib
import pip
from PIL import Image

# Configuration variables
CONFIGURATION_FILE_PATH = "configuration.json"
DEBUG = False

# Console management
class Colors:
	bold='\033[01m'
	black='\033[30m'
	red='\033[31m'
	green='\033[32m'
	blue='\033[34m'
	purple='\033[35m'
	cyan='\033[36m'
	lightgrey='\033[37m'
	darkgrey='\033[90m'
	lightred='\033[91m'
	lightgreen='\033[92m'
	yellow='\033[93m'
	lightblue='\033[94m'
	pink='\033[95m'
	lightcyan='\033[96m'
	end='\033[0m'

def printColoured (color, str):
	print (color + str + Colors.end)

def clear ():
	os.system ("cls" if os.name == "nt" else "clear")

# Utils
def reversePackage (package):
	return ".".join (package.split (".")[::-1])

def moveFolderContents (source, destination):
	for item in os.listdir (source):
		shutil.move (os.path.join (source, item), os.path.join (destination, item))

def getRunningOS ():
	operatingSystem = platform.system ().lower ()

	if operatingSystem == "windows" or operatingSystem == "win32" or operatingSystem == "win64":
		return "windows"
	elif operatingSystem == "darwin":
		return "macos"

def normalizePath (path):
	return path.replace ("\\", os.sep)

def deleteFile (path):
	if os.path.exists (path): 
		os.remove (path)

def readConfigurationFile ():
	printColoured (Colors.purple, "Reading configurations...")

	# Load file and parses it to JSON
	configuration = json.loads (open (CONFIGURATION_FILE_PATH).read ())

	# Localize paths within json
	for attribute in configuration:
		if "path" in attribute:
			configuration[attribute] = normalizePath (configuration[attribute])

	# Append build tools version to object
	configuration["buildToolsVersion"] = extractBuildToolsFromGradle (configuration["application_path"])

	return configuration

def getAndroidSdkPath ():
	operatingSystem = getRunningOS ()
	if operatingSystem == "windows":
		return os.path.expandvars ("%userprofile%") + normalizePath ("\\AppData\\Local\\Android\\Sdk\\build-tools")
	elif operatingSystem == "macos":
		return normalizePath ("~\\Library\\Android\\sdk\\build-tools")

def getAdbPath ():
	operatingSystem = getRunningOS ()
	if operatingSystem == "windows":
		return os.path.expandvars ("%userprofile%") + normalizePath ("\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe")
	elif operatingSystem == "macos":
		return normalizePath ("~\\Library\\Android\\sdk\\platform-tools\\adb")


def extractBuildToolsFromGradle (applicationPath):
	printColoured (Colors.purple, "Extracting buildToolsVersion...")
	# Make path
	gradlePath = os.path.join (applicationPath, normalizePath ("app\\build.gradle"))
	# Read file
	gradleText = open (gradlePath).read ()
	# Searches for buildToolsVersion and its version
	search = re.search ("buildToolsVersion '([0-9\\.]+)'", gradleText)
	# If found, extract from regex matches
	if search: return search.group (1)
	else: raise "Build tools version not found in module build.gradle file"

def executeComand (process, arguments):
	try:
		command = process + " " + arguments
		printColoured (Colors.yellow, command)
		# Create a new process
		processResult = subprocess.run (command, shell=True, check=True, universal_newlines=True)

		if processResult.returncode == 0:
			return "OK"
		elif processResult.returncode == 1:
			return "Process failed\n" + processResult.stderr
	except subprocess.CalledProcessError as e:
		if e.output != None:
			return "Process failed\n" + e.output
		else:
			 return "Process failed"

# Icons methods
def generateApplicationLauncherIcons (configuration):
	printColoured (Colors.purple, "Starting icon resizing...")

	# Localize the paths
	iconPath = os.path.abspath (configuration["application_icon_path"])
	mipmapFolder = os.path.abspath (os.path.join (configuration["application_path"], normalizePath ("app\\src\\main\\res\\mipmap")))

	# Define the dimensions
	dimensions = (
			('xxxhdpi', (192, 192)),
			('xxhdpi', (144, 144)),
			('xhdpi', (96, 96)),
			('hdpi', (72, 72)),
			('mdpi', (48, 48))
		)
	
	# For each resolution, generate an image
	for (resolution, size) in dimensions:
		print ("Resizing icon to %s" % resolution)
		# Resize the image
		image = Image.open (iconPath)
		image.thumbnail (size, Image.ANTIALIAS)

		# Check if the output path exists, if don't create it
		outputPath = mipmapFolder + "-" + resolution
		if not os.path.exists (outputPath):
			os.mkdir (outputPath)

		# Save image
		image.save (os.path.join (outputPath, "ic_launcher.png"), "PNG")

	printColoured (Colors.green, "All resolutions generated successfully")

# Build methods
def executeGradleCommand (applicationPath, arguments):
	operatingSystem = getRunningOS ()

	permission = "sudo " if operatingSystem != "windows" else ""
	
	applicationPath = os.path.abspath (applicationPath)
	executableFile = "gradlew.bat" if operatingSystem == "windows" else "gradlew"
	gradlePath = '"' + os.path.join (applicationPath, executableFile) + '"'
	buildFolder = '"' + applicationPath + '"'
	# Start the process
	result = executeComand (permission + gradlePath + ' -p ' + buildFolder, arguments)
	# Handle the process result
	if result != "OK":
		raise result
	else:
		return "OK"

def listBuildTasks (applicationPath):
	arguments = "tasks --all"
	executeGradleCommand (applicationPath, arguments)

def copyApk (outputFolder, buildType, destinationName=None):
	printColoured (Colors.purple, "\nStarting APK copy...")

	# Show information about the generated apk
	outputJson = json.loads (open (os.path.join (outputFolder, "output.json")).read ())
	print ("Info: ")
	print ("BuildType: " + buildType)
	print ("VersionCode: " + str (outputJson[0]["apkInfo"]["versionCode"]))
	print ("versionName: " + outputJson[0]["apkInfo"]["versionName"])

	# Define the sourcePath and destinationPath
	sourceApkPath = os.path.join (outputFolder, outputJson[0]["path"])
	destinationApkPath = os.path.abspath (normalizePath (".\\generated"))

	# If the destination path doesn't exists, create
	if not os.path.exists (destinationApkPath):
		os.makedirs (destinationApkPath)

	if destinationName == None:
		destinationName = buildType + ".apk"

	destinationApkPath = os.path.join (destinationApkPath, destinationName)

	# If the file already exists, delete it
	if os.path.exists (destinationApkPath):
		printColoured (Colors.lightgrey, "Destination APK already exists! Starting deletion...")
		os.remove (destinationApkPath)

	shutil.copyfile (sourceApkPath, destinationApkPath) 

def buildAppRelease (configuration):
	# Extract info from configuration
	applicationPath = configuration["application_path"]
	keystorePath = configuration["signing_keystore_path"]
	keystorePassword = configuration["signing_keystore_password"]   
	password = configuration["signing_password"]
	# Declare paths to use later on
	buildFolder = os.path.abspath (os.path.join (applicationPath, normalizePath ("app\\build\\outputs\\apk\\release")))
	pathReleaseAPK = os.path.join (buildFolder, "apk-release.apk")
	pathReleaseUnsignedAPK = os.path.join (buildFolder, "app-release-unsigned.apk")
	pathReleaseUnsignedAlignedAPK = os.path.join (buildFolder, "app-unsigned-aligned.apk")
	androidSDK = os.path.join (getAndroidSdkPath (), configuration["buildToolsVersion"])

	# Do build - release
	executeGradleCommand (applicationPath, "assembleRelease")
	
	printColoured (Colors.purple, "Starting APK signing...")

	# Verify if the file exists
	deleteFile (pathReleaseUnsignedAlignedAPK)
	# Align APK     
	result = executeComand (
			os.path.join (androidSDK, "zipalign"), 
			"%s -p 4 \"%s\" \"%s\"" % (
					"-v" if DEBUG else "", # Verbose flag if is DEBUGGING
					pathReleaseUnsignedAPK,
					pathReleaseUnsignedAlignedAPK
				)
		) 
	if result != "OK": raise "Failed to align APK"
	printColoured (Colors.green, "APK Aligned")
	

	# Verify if the file exists
	deleteFile (pathReleaseAPK)
	# Sign APK  
	result = executeComand (
			os.path.join (androidSDK, "apksigner"),
			"sign %s --ks %s --ks-pass pass:%s --key-pass pass:%s --out \"%s\" \"%s\"" % (
				"-v" if DEBUG else "", # Verbose flag if is DEBUGGING
				'"' + os.path.abspath (keystorePath) + '"',
				keystorePassword,
				password,
				pathReleaseAPK,
				pathReleaseUnsignedAlignedAPK
			)
		)
	if result != "OK": raise "Failed to sign APK"
	printColoured (Colors.green, "APK Signed")

	# Verify APK
	executeComand (
			os.path.join (androidSDK, "apksigner"), 
			"verify %s \"%s\"" % (
				"-v" if DEBUG else "", # Verbose flag if is DEBUGGING
				pathReleaseAPK
			)
		)
	if result != "OK": raise "Failed to verify APK"
	printColoured (Colors.green, "APK Verified successfully")

	# -- Copy APK
	try: 
		buildFolder = os.path.join (applicationPath, "app\\release")
		copyApk (buildFolder, "release", "app-release.apk") 

		return "app-release.apk" 
	except: 
		raise "Copy failed" 
	else: 
		printColoured (Colors.green, "APK coppied successfully")

def buildAppDebug (applicationPath):
	# -- Do build
	arguments = "assembleDebug"
	executeGradleCommand (applicationPath, arguments)
	printColoured (Colors.green, "Build debug generated successfully")

	# -- Copy APK
	try: 
		buildFolder = os.path.join (applicationPath, normalizePath ("app\\build\\outputs\\apk\\debug"))
		copyApk (buildFolder, "debug") 

		return "debug.apk" 
	except: 
		raise "Copy failed" 
	else: 
		printColoured (Colors.green, "APK coppied successfully")
	
def buildApp (configuration):
	# List the possibles gradle tasks
	# listBuildTasks (applicationPath)

	if configuration["build_type"] == "release":
		return buildAppRelease (configuration)
	elif configuration["build_type"] == "debug":
		return buildAppDebug (configuration["application_path"])

def installApp (apkFilename, configuration):
	try:
		# Mount the apk file path
		apkPath = os.path.join (os.getcwd (), normalizePath ("generated\\%s" % apkFilename))
		packageName = configuration["application_package_name"]

		# Install apk on any connected device
		result = executeComand (getAdbPath (), "install -r \"%s\"" % apkPath)
		if result != "OK": raise ("Wasn't possible to install the apk on a device")
		else: printColoured (Colors.green, "APK installed successfully")

		# Start application on any connected device
		result = executeComand (getAdbPath (), "shell monkey -p %s -c android.intent.category.LAUNCHER 1" % packageName)

		if result != "OK": raise ("Wasn't possible to start the app on a device")
		else: printColoured (Colors.green, "Starting app on connected device...")			
	except Exception as e:		
		printColoured (Colors.red, e)
		
# Application package renaming
def extractPackageNameFromGradle (applicationPath):
	printColoured (Colors.purple, "Extracting applicationId...")
	# Make path
	gradlePath = os.path.join (applicationPath, normalizePath ("app\\build.gradle"))
	# Read file
	gradleText = open (gradlePath).read ()
	# Searches for applicationId and its version
	search = re.search ("applicationId ['\"](.*?)['\"]", gradleText)
	# If found, extract from regex matches
	if search: 
		return search.group (1)
	else: raise "Application ID not found in module build.gradle file"

def replacePackageRecursive (src, reversedOldPackageName, oldPackageName, reversedNewPackageName, newPackageName, identation=""):
	for item in os.listdir (src):
		path = os.path.join (src, item)

		# Check if is either a Folder or a File
		if os.path.isdir (path):
			# If a Folder, scan its children
			
			if not item in ("build", "release"):
				printColoured (Colors.cyan, "%sFolder [%s]" % (identation, item))
				replacePackageRecursive (path, reversedOldPackageName, oldPackageName, reversedNewPackageName, newPackageName, identation + "  ")
		else:
			# Extract file extension
			fileExtension = path.split (".")[-1]

			# Only do refactor in supported file extensions
			if fileExtension in ("xml", "java", "gradle"):
				# If a File, Replace every occourence of old package name
				printColoured (Colors.lightcyan, "%sFile [%s]" % (identation, item))

				# Opens file
				file = open (path, 'r+')

				# Read file's content and refactor packages
				fileText = file.read ()
				file.seek (0)		
				fileText = fileText.replace (oldPackageName, newPackageName)
				fileText = fileText.replace (reversedOldPackageName, reversedNewPackageName)

				# Write new text to file
				file.write (fileText)

				# Close file
				file.truncate ()
				file.close ()

def createNewPackgeFolderStructure (applicationPath, oldPackageName, newPackageName):
	printColoured (Colors.purple, "Generating new folder structure...")
	
	oldFolderStructure = oldPackageName.split (".")
	newFolderStructure = newPackageName.split (".")

	folders = ["main", "androidTest", "test"]

	for folder in folders:
		sourcePath = os.path.abspath (os.path.join (applicationPath, normalizePath ("app\\src\\%s\\java" % folder)))

		# Generate new folder structure
		newPath = os.path.join (sourcePath, os.sep.join (newFolderStructure))
		os.makedirs (newPath)

		# Move everything
		oldPath =  os.path.join (sourcePath, os.sep.join (oldFolderStructure))
		moveFolderContents (oldPath, newPath)

		# Delete old folder structure
		shutil.rmtree (os.path.join (sourcePath, oldFolderStructure[0]))

def renameAppPackageName (configuration):	
	# Get old package name
	applicationPath = configuration["application_path"]
	oldPackageName = extractPackageNameFromGradle (applicationPath)
	newPackageName = configuration["application_package_name"]

	# Ignore if we got the same packageNaming
	if not oldPackageName != newPackageName: return

	printColoured (Colors.purple, "Refactoring application package name...")

	# Reverse the package naming order
	reversedOld = reversePackage (oldPackageName)
	reversedNew = reversePackage (newPackageName)

	# Rename all files containing that package name, overide it to 'new package name'
	replacePackageRecursive (os.path.join (applicationPath, "app"), reversedOld, oldPackageName, reversedNew, newPackageName)

	# Generates a new folder structure and deletes the old one
	createNewPackgeFolderStructure (applicationPath, oldPackageName, newPackageName)

#---------------------------------------------------#
# Main                                              #
#---------------------------------------------------#
try:
	# Print header
	clear ()
	printColoured (Colors.bold, "--Android auto release--")
	printColoured (Colors.purple, "Starting...")

	# Searches for the configuration file
	configuration = readConfigurationFile ()

	# Handle application icon
	if configuration.get ("application_icon_path"):
		generateApplicationLauncherIcons (configuration)

	# Handle application package naming
	if configuration.get ("application_package_name"):
		renameAppPackageName (configuration)

	# Tries to build the application using the configuration file
	apkFilename = buildApp (configuration)

	# Tries to run the app if has any available phone
	installApp (apkFilename, configuration)
except Exception as e:
	printColoured (Colors.red, "Error ocurred!")
	sys.exit (e)