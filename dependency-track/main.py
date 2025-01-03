# python based script
# upload_sbom.py
import os
import subprocess
import re
import sys
import json
# Function to check and install the 'requests' module if not already installed
def install_requests():
    try:
        import requests
    except ImportError:
        print("Requests module not found. Installing it now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests

# Ensure 'requests' is installed
install_requests()



def parse_scm_url(scm_url):
    """
    Extract SCM source, namespace, and repository from a given SCM URL.

    Args:
        scm_url (str): The SCM URL.

    Returns:
        dict: A dictionary with keys 'source', 'namespace', and 'repo'.
    """
    pattern = r"^(?:http(?:s)?://)?(?:\S+@)?(?P<source>[^/]+)/(?P<namespace>[^/]+)/(?P<repo>[^/]+?)(?=\.git|$)"
    match = re.match(pattern, scm_url)

    if match:
        return  match.group("source") + "/" + match.group("namespace") + "/" + match.group("repo")
        
    else:
        raise ValueError("Invalid SCM URL format")









import requests
from io import BytesIO



DEPENDENCY_TRACK_HOST =  os.getenv("DEPENDENCY_TRACK_HOST" , None)
DEPENDENCY_TRACK_API_KEY =  os.getenv("DEPENDENCY_TRACK_API_KEY" , None)
output_file_path =  os.getenv("upload_response_file_path" , None)
repository_path = os.getenv("repository_url" , None)
sca_bom_file = os.getenv("sbom_file_path" , None)




if not DEPENDENCY_TRACK_HOST:
    raise Exception("Missing env variable  `DEPENDENCY_TRACK_HOST` ")

if not DEPENDENCY_TRACK_API_KEY:
    raise Exception("Missing env variable  `DEPENDENCY_TRACK_API_KEY` ")

print("DEPENDENCY_TRACK_HOST", DEPENDENCY_TRACK_HOST)
print("DEPENDENCY_TRACK_API_KEY", DEPENDENCY_TRACK_API_KEY)

print("OUTPUT_FILE_PATH" , output_file_path )


if not repository_path :
    raise Exception("No 'repository_path' provided via environment!")

print("REPOSITORY_PATH", repository_path)




print("SCA_BOM_FILE", sca_bom_file)
if not sca_bom_file :
    raise Exception("No SBOM file found!")

with open ( sca_bom_file , "r") as file:
    result  = file.readlines()



# Synchronous function
def upload_bom_sca(project_name, bom_file_path):
    url = f"{DEPENDENCY_TRACK_HOST}/api/v1/bom"
    
    # Read the BOM file content
    with open(bom_file_path, "rb") as file:
        bom_content = file.read()

    # Convert the BOM content to a file-like object
    bom_file = BytesIO(bom_content)



    payload = {
        'autoCreate': 'true',
        'projectName': project_name,
        'projectVersion': 'latest'
    }

    files = {
        'bom': ('bom.json', bom_file, 'application/json')
    }

    headers = {
        'Accept': 'application/json',
        'X-Api-Key': DEPENDENCY_TRACK_API_KEY
    }

    response = requests.post(url, headers=headers, data=payload, files=files)
    
    try:
        response = { "project_name": project_name,   "status": response.status_code , "response":  response.json() }
    except:
        response = { "project_name": project_name,  "status": response.status_code , "response":  response.content   }
        raise Exception("Failed to upload")
        

    if output_file_path:
        json.dump( response,   open(output_file_path, "w" ,))
        
    
    
    return response


project_name = parse_scm_url(repository_path)
print("PROJECT_NAME", project_name)

print("Status: Uploading to Dependency Track")
upload_bom_sca(project_name, sca_bom_file)

