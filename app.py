import io
from flask import Flask, request, jsonify, send_file, session
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import requests
from werkzeug.utils import secure_filename
from googleapiclient.http import MediaIoBaseUpload,MediaIoBaseDownload
from io import BytesIO
from flask_cors import CORS
from googleapiclient.errors import HttpError
from flask_bcrypt import Bcrypt
from models import db, Outlet,OutletReviews,ClientReviews




app = Flask(__name__)
CORS(app, origins=["https://file-share-frontend-chi.vercel.app","http://localhost:3000"])

app.config['SECRET_KEY'] = 'password'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flaskdb.db'

app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://appsnetic_user:Usjgghl8YqBZ5cUBq0u9kYDGzWp8VZif@dpg-cneutaol5elc73ddoo10-a.oregon-postgres.render.com/appsnetic"

SQLALCHEMY_TRACK_MODIFICATION = False
SQLALCHEMY_ECHO = True

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE ='service_account.json'
PARENT_FOLDER_ID ="11l9rxQFj9fTo8rFsRXVioBnvYFEEmDok"
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx'}



bcrypt = Bcrypt(app)
db.init_app(app)

with app.app_context():
    db.create_all()


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

# Registration////////////////////////////////////////////////////////////////////////////////

@app.route("/register", methods=["POST"])
def register_outletPartner():
    outletName = request.json["outletName"]
    outletOwnerName = request.json["outletOwnerName"]
    landMark = request.json["landMark"]
    outletPhoneNumber = request.json["outletPhoneNumber"]
    outletPassword = request.json["outletPassword"]
    outletUrl = request.json["outletUrl"]

    outlet_exists = Outlet.query.filter_by(outletPhoneNumber=outletPhoneNumber).first()

    if outlet_exists:
        return jsonify({
            "success": False,
            "body": {
                "error": "Outlet Partner with this Phone Number Already Exists"
            }
        }), 409
    else:
        hashed_password = bcrypt.generate_password_hash(outletPassword).decode('utf-8')  # Ensure the hash is a string
        new_outlet = Outlet(outletName=outletName, outletOwnerName=outletOwnerName, landMark=landMark,
                             outletPhoneNumber=outletPhoneNumber, outletPassword=hashed_password, outletUrl=outletUrl)
        db.session.add(new_outlet)
        db.session.commit()
        session["outlet_id"] = new_outlet.id

        return jsonify({
            "success": True,
            "body": {
                "outletName": new_outlet.outletName,
                "outletOwnerName": new_outlet.outletOwnerName,
                "landMark": new_outlet.landMark,
                "outletPhoneNumber": new_outlet.outletPhoneNumber,
                "outletPassword": outletPassword, 
                "outletUrl": new_outlet.outletUrl,
            }
        }), 200
# Login //////////////////////////////////////////////////////////////////////////////////////////////

@app.route("/login", methods=["POST"])
def login_outletPartner():
    outletPhoneNumber = request.json["outletPhoneNumber"]
    outletPassword = request.json["outletPassword"]

    outlet_user = Outlet.query.filter_by(outletPhoneNumber=outletPhoneNumber).first()

    if outlet_user is None or not bcrypt.check_password_hash(outlet_user.outletPassword, outletPassword):
        return jsonify({
            "success": False,
            "body": {
                "error": "Invalid Outlet Partner PhoneNumber or Password"
            }
        }), 401
    else:
        session["outlet_id"] = outlet_user.id

        return jsonify({
            "success": True,
            "body": {
                "id": outlet_user.id,
                "outletName": outlet_user.outletName,
                "outletOwnerName": outlet_user.outletOwnerName,
                "outletPhoneNumber": outlet_user.outletPhoneNumber,
                "outletUrl": outlet_user.outletUrl
            }
        }), 200

# Create folder with Phone Number Name/////////////////////////////////////////////////////////////////////////////

def authenticate():
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return creds

def create_or_get_folder(service, parent_folder_id, folder_name):
    file_list = service.files().list(q="mimeType='application/vnd.google-apps.folder' and name='" + folder_name + "' and '" + parent_folder_id + "' in parents",
                                     spaces='drive',
                                     fields='files(id, name)').execute()
    if len(file_list.get('files', [])) > 0:
        # Folder exists, return its ID
        return file_list['files'][0]['id']
    else:
        # Folder doesn't exist, create it
        folder_metadata = {
            'name': folder_name,
            'parents': [parent_folder_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Upload files into phone number folder ///////////////////////////////////////////////////
@app.route("/upload", methods=['POST'])
def upload_to_drive():
    phone_number = request.args.get('phoneNumber')
    user_name = request.form.get('userName')

    if 'file0' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    files = []
    i = 0

    while f'file{i}' in request.files:
        file = request.files[f'file{i}']
        files.append(file)
        i += 1

    if not files:
        return jsonify({'error': 'No files selected'}), 400

    # Authenticate with Google Drive
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Create or get the folder ID based on the phone number
    folder_id = create_or_get_folder(service, PARENT_FOLDER_ID, phone_number)

    for i, file in enumerate(files):
        if file and allowed_file(file.filename):
            # Read the content into a BytesIO object
            file_content = BytesIO(file.read())

            # Upload each file to the folder
            file_metadata = {
                'name': secure_filename(file.filename),
                'parents': [folder_id]
            }

            media = MediaIoBaseUpload(file_content, mimetype=file.content_type)

            try:
                uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

                # Update the file name with the username
                new_file_name = f"{secure_filename(file.filename)}-{user_name}"
                service.files().update(fileId=uploaded_file['id'], body={'name': new_file_name}).execute()

            except HttpError as error:
                print(f"An error occurred during file upload: {error}")
                return jsonify(
                    { "success": False,'error': 'File upload failed'}
                    ), 500

    return jsonify(
        {"success": True,
         'message': 'Files uploaded successfully'}
        ), 200

# Creating a saved folder for saved files ////////////////////////////////////////////////////////////////////////////////////////////////////////

@app.route("/create_folder", methods=['POST'])
def create_folder():
    phone_number = request.args.get('phoneNumber')
    folder_name = request.args.get('folder')
    file_id = request.args.get('fileId')

    if not phone_number or not folder_name or not file_id:
        return jsonify({'error': 'Phone number, folder name, and file ID are required'}), 400

    # Authenticate with Google Drive
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Get the folder ID based on the phone number
    parent_folder_id = create_or_get_folder(service, PARENT_FOLDER_ID, phone_number)

    # Create the specified folder within the user's folder
    folder_id = create_or_get_folder(service, parent_folder_id, folder_name)

    # Move the specified file to the new folder
    move_file(service, file_id, folder_id)

    return jsonify({'success': True, 'message': f'File with ID {file_id} moved to folder "{folder_name}" successfully'}), 200

def move_file(service, file_id, new_folder_id):
    # Retrieve the existing parents to remove from the file
    file = service.files().get(fileId=file_id,
                                fields='parents').execute()
    previous_parents = ",".join(file.get('parents'))

    # Move the file to the new folder
    file = service.files().update(fileId=file_id,
                                  addParents=new_folder_id,
                                  removeParents=previous_parents,
                                  fields='id, parents').execute()

    return file


# Get all files in Phone Number folder/////////////////////////////////////////////////////////////////////////////////////////////////////

def get_files_in_folder(service, folder_id):
    results = service.files().list(q=f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'",
                                   fields="files(id, name)").execute()
    files = results.get('files', [])
    return files

@app.route("/getfiles", methods=['GET'])
def get_files():
    phone_number = request.args.get('phoneNumber')

    # Authenticate with Google Drive
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Get the folder ID based on the phone number
    folder_id = create_or_get_folder(service, PARENT_FOLDER_ID, phone_number)

    # Get all files in the folder
    files = get_files_in_folder(service, folder_id)

    # Create a response with file information
    response = []
    for file in files:
        original_filename = file['name']
        username = get_username_from_filename(original_filename)
        clean_filename = original_filename.rsplit('-', 1)[0]
        file_info = {
            'file_id': file['id'],
            'filename': clean_filename,
            'username': username,
        }
        response.append(file_info)

    return jsonify({'success':True,'body': response})

def get_username_from_filename(filename):
    # Assume the username is after the last '-' in the filename
    return filename.rsplit('-', 1)[-1].split('.')[0]


def delete_file(file_id):
    creds = authenticate()

    try:
        service = build("drive", "v3", credentials=creds)
        service.files().delete(fileId=file_id).execute()
        return jsonify({'success': True,'message': f'File with ID {file_id} deleted successfully'})

    except HttpError as error:
        return jsonify({'success': False,'error': f'An error occurred during file deletion: {error}'}), 500

# Delete a file //////////////////////////////////////////////////////////////////////////////////////////////////////
@app.route("/delete", methods=['DELETE'])
def delete():
    file_id = request.args.get('file_id')

    if not file_id:
        return jsonify({'success': False,'error': 'File ID not provided'}), 400

    return delete_file(file_id)


def download_file(file_id, folder_id=None):
    """Downloads a file from Google Drive."""
    creds = authenticate()

    try:
        service = build("drive", "v3", credentials=creds)

        # Get file metadata to obtain the original filename
        file_metadata = service.files().get(fileId=file_id).execute()
        original_filename = file_metadata['name']

        # Remove the username suffix, if present
        clean_filename = original_filename.rsplit('-', 1)[0]

        # Create a media request to download the file
        request = service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False

        while done is False:
            status, done = downloader.next_chunk()

        # Seek to the beginning of the BytesIO buffer
        file.seek(0)

        return send_file(
            file,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=clean_filename
        )
        
    except HttpError as error:
        print(f"An error occurred: {error}")
        return jsonify({'error': 'File download failed'}), 500
    
# Download Files ///////////////////////////////////////////////////////

@app.route("/download", methods=['GET'])
def download():
    file_id = request.args.get('file_id')

    if not file_id:
        return jsonify({'error': 'File ID not provided'}), 400

    return download_file(file_id)

# Show all saved files///////////////////////////////////////////////////////
@app.route("/get_saved_files", methods=['GET'])
def get_saved_files():
    phone_number = request.args.get('phoneNumber')

    if not phone_number:
        return jsonify({'error': 'Phone number is required'}), 400

    # Authenticate with Google Drive
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Get the folder ID based on the phone number
    parent_folder_id = create_or_get_folder(service, PARENT_FOLDER_ID, phone_number)

    # Get the folder ID for the "saved" folder
    saved_folder_id = create_or_get_folder(service, parent_folder_id, 'saved')

    # Get all files in the "saved" folder
    saved_files = get_files_in_folder(service, saved_folder_id)

    # Create a response with file information
    response = []
    for file in saved_files:
        original_filename = file['name']
        username = get_username_from_filename(original_filename)
        clean_filename = original_filename.rsplit('-', 1)[0]
        file_info = {
            'file_id': file['id'],
            'filename': clean_filename,
            'username': username,
        }
        response.append(file_info)

    return jsonify({'success': True, 'body': response})


# Delete from saved folder///////////////////////////////////////////////////////


@app.route("/delete_saved_file", methods=['DELETE'])
def delete_saved_file():
    file_id = request.args.get('file_id')

    if not file_id:
        return jsonify({'error': 'File ID is required'}), 400

    # Authenticate with Google Drive
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Get the folder ID based on the phone number
    phone_number = request.args.get('phoneNumber')
    parent_folder_id = create_or_get_folder(service, PARENT_FOLDER_ID, phone_number)

    try:
        # Get the "saved" folder ID
        saved_folder_id = create_or_get_folder(service, parent_folder_id, "saved")

        # Delete the file from the "saved" folder
        service.files().delete(fileId=file_id).execute()

        return jsonify({'success': True, 'message': f'File with ID {file_id} deleted from "saved" folder successfully'})

    except HttpError as error:
        return jsonify({'error': f'An error occurred during file deletion: {error}'}), 500


# Download saved file ////////////////////////////////////////

@app.route("/download_saved_file", methods=['GET'])
def download_saved_file():
    phone_number = request.args.get('phoneNumber')
    file_id = request.args.get('file_id')

    if not phone_number or not file_id:
        return jsonify({'error': 'Phone number or file ID not provided'}), 400

    # Authenticate with Google Drive
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Get the folder ID for the "saved" folder
    saved_folder_id = create_or_get_folder(service, PARENT_FOLDER_ID, f"{phone_number}/saved")

    try:
        # Download the file from the "saved" folder
        return download_file(file_id, saved_folder_id)
    
    except HttpError as error:
        print(f"An error occurred: {error}")
        return jsonify({'error': 'File download failed'}), 500




@app.route("/save_review", methods=["POST"])
def save_review():
    try:
        outlet_name = request.json.get("outlet_name", None)
        question_1 = request.json.get("fileManagementOption", None)
        question_2 = request.json.get("performanceOption", None)
        question_3 = request.json.get("taskEasierOption", None)
        question_4 = request.json.get("currentValue", None)
        comment = request.json.get("comment", None)

        review = OutletReviews(
            outletName=outlet_name,
            question_1=question_1,
            question_2=question_2,
            question_3=question_3,
            question_4=question_4,
            comment=comment
        )

        db.session.add(review)
        db.session.commit()

        return jsonify({"success": True, "message": "Review saved successfully"}), 200

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"success": False, "error": "Error saving review"}), 500
    
    
    
@app.route("/save_client_review", methods=["POST"])
def save_client_review():
    try:
        client_name = request.json.get("client_name", None)
        question_1 = request.json.get("currentValue", None)
        question_2 = request.json.get("performanceOption", None)
        question_3 = request.json.get("scanOption", None)


        review = ClientReviews(
            clientName=client_name,
            question_1=question_1,
            question_2=question_2,
            question_3=question_3,

        )

        db.session.add(review)
        db.session.commit()

        return jsonify({"success": True, "message": "Review saved successfully"}), 200

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"success": False, "error": "Error saving review"}), 500
    
    
    


@app.route('/send_otp', methods=['POST'])
def send_otp():
    # Get data from the request
    data = request.json
    phone_number = data.get('phoneNumber')
    otp_code = data.get('code')  

    # Prepare the payload for the SMS API
    payload = {
        'variables_values': otp_code,
        'route': 'otp',
        'numbers': phone_number
    }

    # Set your Fast2SMS API key
    headers = {
        'authorization': '56QNSqVTRMZ2AfBX1usaWOz7vl3JYrktgIxyiKUjcDwnhb8medlO4aI5ETyUidCR3NQLW0bsBPg9u28c',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'no-cache',
    }

    # Make a request to the Fast2SMS API
    url = "https://www.fast2sms.com/dev/bulkV2"
    response = requests.post(url, data=payload, headers=headers)

    # Check if the message was sent successfully
    if response.json().get('return') == True:
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to send OTP'})
    
    

if __name__ == "__main__":
    app.run(debug=True)
