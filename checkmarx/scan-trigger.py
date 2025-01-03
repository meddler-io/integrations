# Install libs
# Function to check and install the 'requests' module if not already installed
import subprocess
import sys

dependencies_list = ["requests" , "requests-toolbelt", "tqdm", "python-dotenv"]

def install_dependencies():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install" ] + dependencies_list  )
    except:
        print("Requests module not found. Installing it now...")
        raise Exception("Could not initate the parers. Dependencies missing!")


# Ensure 'requests' is installed
install_dependencies()


# Start scan
import json
import os
import re
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from tqdm import tqdm
import os
import time
from dotenv import load_dotenv
load_dotenv()
import os
import zipfile
import requests



host = os.getenv("CHECKMARX_HOST")
username = os.getenv("CHECKMARX_USERNAME")
password = os.getenv("CHECKMARX_PASSWORD")
CHECKMARX_CLIENT_SECRET = os.getenv("CHECKMARX_CLIENT_SECRET")
CHECKMARX_RESPONSE_PATH = os.environ.get("CHECKMARX_RESPONSE_PATH", "response.json")


# 
folder_to_zip = os.getenv("git_path")
# 
repo_url = os.getenv("REPOSITORY_URL")

# 


print("CHECKMARX_HOST", host)
print("CHECKMARX_USERNAME", username)
print("CHECKMARX_PASSWORD", password)
print("CHECKMARX_CLIENT_SECRET", CHECKMARX_CLIENT_SECRET)
print("REPOSITORY_URL", repo_url)
print("GIT_REPO_TO_ZIP", folder_to_zip)


# 
output_zip = "repository.zip"


# Over ride reuqests to handle retry-mechanism and login, and rate-limitting!
class CustomSessionWithRateLimitngHandler(requests.Session):
    

    
    def __init__(self , delay = 30) -> None:
        self.delay = delay
        self.auth_token = self.login_to_checkmarx()
        super().__init__()
        
    def login_to_checkmarx(self):
        url = f"""{host}/cxrestapi/auth/identity/connect/token"""

        payload = f'username={username}&password={password}&client_id=resource_owner_sast_client&client_secret={CHECKMARX_CLIENT_SECRET}&grant_type=password&scope=access_control_api sast_api'
        headers = {
        'Accept': 'application/json;v=1.0',
        'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        access_token = response.json()
        
        access_token =  access_token["access_token"]
        return access_token 

        
    def request(self, method, url, **kwargs):
        
        while True:
            
            _headers = kwargs.get('headers', {}) 
            _headers["Authorization"] = f'Bearer {self.auth_token}'
            kwargs['headers'] = _headers
            
            
            response = super().request(method, url, **kwargs)
            
            # Check for rate limiting
            if response.status_code == 429:  # Too Many Requests
                print(f"Rate limit exceeded. Retrying in {self.delay} seconds...")
                time.sleep(self.delay)  # Wait for 10 seconds before retrying
                continue  # Retry the request
            

            elif response.status_code == 401:  # Too Many Requests
                self.auth_token = self.login_to_checkmarx()

                
                
                print(f"Token invalid / expired. Retrying in {4} seconds...")
                time.sleep(4)  # Wait for 10 seconds before retrying
                continue  # Retry the request
            
            
            
            
            # If the request was successful or failed for another reason, break the loop
            # response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
            return response  # Return the successful response


requests = CustomSessionWithRateLimitngHandler()


def stream_file_to_checkmarx( project_id: int, file_name: str , commit_id : str , commit_date : str):
    url = f"{host}/cxrestapi/sast/scanWithSettings"
    headers = {
        'Accept': 'application/json;v=1.0',
    }

    # Get the total file size for tqdm progress bar
    total_size = os.path.getsize(file_name)
    
    with open(file_name, "rb") as file, tqdm(total=total_size, unit="B", unit_scale=True, desc="Uploading") as tqdm_bar:
        # file_reader = TqdmFileReader(file, tqdm_bar)
        
        # MultipartEncoder for streaming with progress tracking
        encoder = MultipartEncoder(
            fields={
                'projectId': str(project_id),
                'overrideProjectSetting': 'true',
                
                'comment':  json.dumps( { "commit_id": commit_id , "commit_date": commit_date } )  ,
                'isIncremental': 'false',
                'forceScan': 'true',
                'zippedSource': ('source-code.zip', file, 'application/zip')
            }
        )
        
        def callback(monitor):
            tqdm_bar.update(monitor.bytes_read - tqdm_bar.n)\
                
        encoder = MultipartEncoderMonitor(encoder, callback)
        
        headers['Content-Type'] = encoder.content_type  # Set the correct content-type
        
        # Send the request with progress tracking
        with requests.post(url, headers=headers, data=encoder, stream=True) as response:
            if response.status_code == 201:
                scan_id = response.json().get("id")
                
                return response.content
                return scan_id
            else:
                print(f'Failed to upload to Checkmarx: {response.status_code} {response.text}')
                return response.content
                

# Example usage
# scan_bitbucket_repo(access_token, code_repository)


def create_project(project_name: str , teamId: int):
    url = f"""{host}/cxrestapi/projects"""

    headers = {
        'Accept': 'application/json;v=1.0',
        # 'Content-Type': 'application/x-www-form-urlencoded'
    }

    data = {
        "name": project_name,
        "owningTeam": teamId,  # team name :  bitbucket
        "isPublic": True
    }

    response = requests.post(url, headers=headers, json=data)
    print(url, data, response.content)
    data = response.json()

    return get_project(project_name , teamId)




def get_project(project_name: str , team_id: int):
    
        
    url = f"""{host}/cxrestapi/projects"""

    headers = {

        'Accept': 'application/json;v=1.0',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    response = requests.get( url, headers=headers)
    data = response.json()


    found_project = next(
        (obj for obj in data if ( obj["name"] == project_name) and obj["teamId"] == team_id) , None)
    

    
    return found_project


def ensure_project(project_name: str , team_id : int):

    project_details = get_project(project_name, team_id)
    if project_details == None:
        print("project not found. Will try to create!", project_name , team_id)
        project_details = create_project(project_name, team_id)

    if project_details == None:
        raise Exception("Failed to create / fetch project")

    # print("project created", project_name, project_details)
    return project_details


def create_team(team_name: str , parent_team_id : int):
    url = f"""{host}/CxRestAPI/auth/teams"""

    headers = {
        'Accept': 'application/json;v=1.0',
        # 'Content-Type': 'application/x-www-form-urlencoded'
    }

    data = {
        "name": team_name,
        "parentId": parent_team_id,  # team name :  bitbucket
        # "isPublic": True
    }
    
    print("create_team", team_name ,parent_team_id)

    response = requests.post(  url, headers=headers, json=data)
    print(response.content , response.status_code, url)

    return get_team(team_name , parent_team_id)



def get_teams():

    url = f"""{host}/cxrestapi/auth/teams"""

    headers = {

        'Accept': 'application/json;v=1.0',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    response = requests.get( url, headers=headers)
    data = response.json()
    
    return data

  

def get_team(team_name: str , parent_team_id : int ):

    url = f"""{host}/cxrestapi/auth/teams"""

    headers = {

        'Accept': 'application/json;v=1.0',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    response = requests.get( url, headers=headers)
    data = response.json()
    

    found_project = next(
        (obj for obj in data if obj["name"].lower() == team_name.lower()  and obj["parentId"] == parent_team_id ), None)
    

    
    return found_project



def ensure_team(team_name: str , parent_team_id : int = 1):

    # get parent team id
    if parent_team_id == None:
        parent_team_id = 1

    team_details = get_team(team_name, parent_team_id)
        
    if team_details == None:
        print("team not found. Will try to create!", team_name)
        team_details = create_team(team_name , parent_team_id)

    if team_details == None:
        raise Exception("Failed to create / fetch team")

    return team_details





def parse_scm_url(scm_url):
    """
    Extract SCM source, namespace, and repository from a given SCM URL.

    Args:
        scm_url (str): The SCM URL.

    Returns:
        dict: A dictionary with keys 'source', 'namespace', and 'repo'.
    """
    pattern = r"^(?:http(?:s)?://)?(?:\S+@)?(?P<source>[^/]+)/(?P<namespace>[^/]+)/(?P<repo>[^.]+)(?:\.git)?$"
    match = re.match(pattern, scm_url)

    if match:
        # Ensure workspace , and project exists. Naming convention will be : namespace@repository. source domain will be team name.
        return  [match.group("source")  ,  match.group("namespace")   ,  match.group("repo") ]
        
        # return  match.group("source") + "/" + match.group("namespace") + "/" + match.group("repo")
        
    else:
        raise ValueError("Invalid SCM URL format")






def zip_folder(folder_path, output_path):
    """
    Zips the contents of the given folder into a zip file at the specified output path,
    skipping symbolic links.

    :param folder_path: Path to the folder to be zipped.
    :param output_path: Path to the output zip file.
    """
    # Ensure the folder exists
    if not os.path.isdir(folder_path):
        print(f"Error: The folder '{folder_path}' does not exist.")
        return False
    
    # Create a zip file
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through the folder and add files to the zip
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Skip symbolic links
                if os.path.islink(file_path):
                    print(f"Skipping symbolic link: {file_path}")
                    continue
                # Get the relative path to maintain folder structure
                relative_path = os.path.relpath(file_path, start=folder_path)
                zipf.write(file_path, arcname=relative_path)
    
    print(f"Folder '{folder_path}' has been zipped into '{output_path}'.")
    return True


def get_git_info(folder_path):
    """
    Retrieves the current branch name and latest commit ID from a Git repository
    without using subprocess.

    :param folder_path: Path to the Git repository folder.
    :return: A tuple containing the branch name and commit ID, or None if not a Git repository.
    """
    git_dir = os.path.join(folder_path, ".git")
    if not os.path.isdir(git_dir):
        print(f"Error: The folder '{folder_path}' is not a Git repository.")
        raise Exception("Invalid git repo!")
        return None , None

    # Read the HEAD file to get the current branch
    head_file = os.path.join(git_dir, "HEAD")
    try:
        with open(head_file, "r") as f:
            ref = f.readline().strip()
            if ref.startswith("ref:"):
                # Extract the branch name from the ref
                branch = ref.split("/")[-1]
                # Get the commit ID from the branch file
                ref_path = os.path.join(git_dir, ref.split(": ")[1])
                with open(ref_path, "r") as ref_file:
                    commit_id = ref_file.readline().strip()
                return branch, commit_id
            else:
                # Detached HEAD; use the commit ID directly
                branch = "DETACHED_HEAD"
                commit_id = ref
                return branch, commit_id
    except Exception as e:
        print(f"Error reading Git information: {e}")
        raise Exception("Invalid git repo!")
        return None , None





# test_url = "https://rounak316@bitbucket.org/daamm/neo.git"
# _ = parse_scm_url(test_url)
# print(_)


# test_url = "https://gitlab.com/studiogangster/cyclops.git"
# _ = parse_scm_url(test_url)
# print(_)


# test_url = "https://code.sli.ke/qa/automation.git"
# _ = parse_scm_url(test_url)
# print(_)
 
if __name__ == "__main__":
    
    hypothetical__team = parse_scm_url(repo_url)

    team_hierarchy = []
    for slug in hypothetical__team:
        for slug in slug.split("/"):
            if len(slug):
                team_hierarchy.append(slug)
        

    project_name = team_hierarchy[-1]
    team_hierarchy = team_hierarchy[:-1]
    
    print("team_hierarchy", project_name)
    print("team_hierarchy",  team_hierarchy)
    
    parent_team_id = None
    
    project_team_id = None
    
    for team_name in team_hierarchy:
        print("ensuring", team_name , parent_team_id)
        ensured_team = ensure_team(  team_name, parent_team_id )
        print("ensured_team", ensured_team)
        print("parent_team_id", ensured_team["id"])
        parent_team_id = ensured_team["id"]
        project_team_id = parent_team_id
        
    project_details = ensure_project(   project_name , project_team_id)
    
        
    project_id = project_details['id']
    
    # Example usage
    
    branch , commit_id = get_git_info(folder_to_zip ) 
    print("get_git_info", branch , commit_id)
    
    
    was_zip_created = zip_folder(folder_to_zip, output_zip)
    
    print("was_zip_created", was_zip_created)
    response = stream_file_to_checkmarx(project_id , output_zip , commit_id, branch)
    print("checkmarx response:" , response)
    
    with open(  CHECKMARX_RESPONSE_PATH  , "wb") as f:
        f.write(response)
    


    
