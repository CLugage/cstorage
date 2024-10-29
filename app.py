from flask import Flask, render_template, redirect, url_for, flash, request, render_template_string
from flask import Flask, request, jsonify, send_from_directory,Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, bcrypt, ActivityLog, File, StoragePlan

import os
import shutil
from datetime import datetime

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_secret_key'
UPLOAD_FOLDER = 'uploads'  # Directory where uploaded files will be stored
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize extensions
db.init_app(app)
bcrypt.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def landing():
    return render_template('landing.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Get the default storage plan (the first plan in the database)
        default_plan = StoragePlan.query.first()  # Assuming you want to assign the first plan

        if default_plan is None:
            flash('No storage plans available. Please contact support.', 'danger')
            return redirect(url_for('register'))

        # Create a new user
        user = User(username=username, email=email)
        user.set_password(password)
        user.storage_plan_id = default_plan.id  # Assign the storage plan to the user
        # user.balance = 100.0

        db.session.add(user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Get the list of files and folders uploaded by the current user
    files = File.query.filter_by(user_id=current_user.id).all()
    return render_template('dash.html', files=files)



@app.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    data = request.get_json()  # Parse the JSON data
    folder_name = data.get('folder_name')
    parent_path = data.get('parent_path', '')  # Get the parent path from the request

    # Validate folder name
    if not folder_name or not folder_name.isalnum():
        return jsonify({'error': 'Invalid folder name. Use alphanumeric characters only.'}), 400

    # Construct the full folder path
    folder_path = os.path.join(UPLOAD_FOLDER, parent_path, folder_name)

    # Check if the folder already exists
    if os.path.exists(folder_path):
        return jsonify({'error': 'Folder already exists.'}), 400

    try:
        os.makedirs(folder_path, exist_ok=True)  # Create the folder
        log_activity(current_user.id, 'created folder', folder_name)  # Log the activity
        return jsonify({'message': 'Folder created successfully', 'folder_name': folder_name}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500



BASE_PATH = 'uploads'

@app.route('/delete_folder', methods=['POST'])
def delete_folder():
    data = request.json
    folder_path = data.get('path')

    # Construct the full path using the BASE_PATH
    full_path = os.path.join(BASE_PATH, folder_path)
    
    app.logger.debug(f"Received request to delete folder: {full_path}")  # Log the received path
    
    if not folder_path:
        return jsonify({'error': 'No path provided for folder deletion.'}), 400

    if not os.path.exists(full_path):
        return jsonify({'error': 'Folder does not exist.'}), 404

    try:
        shutil.rmtree(full_path)  # This will delete the folder and its contents
        app.logger.debug(f"Successfully deleted folder: {full_path}")  # Log success
        return jsonify({'success': True, 'message': 'Folder deleted successfully.'}), 200
    except Exception as e:
        app.logger.error(f"Error deleting folder: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/file_content', methods=['GET'])
@login_required
def file_content():
    file_name = request.args.get('file')
    path = request.args.get('path', '')  # Get the path from the query parameter

    # Sanitize the path (for security)
    if path and '..' in path:
        app.logger.error("Invalid path provided.")
        return jsonify({'error': 'Invalid path'}), 400

    # Construct the full file path
    full_path = os.path.join(UPLOAD_FOLDER, path, file_name) if path else os.path.join(UPLOAD_FOLDER, file_name)
    app.logger.debug(f"Full file path: {full_path}")

    # Check if the file exists
    if not os.path.isfile(full_path):
        app.logger.error(f"File not found: {full_path}")
        return jsonify({'error': 'File not found', 'file': file_name}), 404

    # Read the file content
    try:
        with open(full_path, 'r') as file:
            content = file.read()

        # Return the content as plain text
        return Response(content, mimetype='text/plain')

    except Exception as e:
        app.logger.error(f"Error reading file {file_name}: {str(e)}")
        return jsonify({'error': 'Could not read file', 'details': str(e)}), 500

@app.route('/save/<path:filename>', methods=['POST'])
def save_file(filename):
    """
    Endpoint to save the content of a file.

    Args:
        filename (str): The path to the file to be saved.

    Returns:
        dict: Success message or error message.
    """
    data = request.json
    content = data.get('content')

    if content is None:
        return jsonify({'error': 'No content provided'}), 400

    file_path = os.path.join(BASE_PATH, filename)

    try:
        # Optionally, check if the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w') as f:
            f.write(content)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': f'An error occurred while saving the file: {str(e)}'}), 500



@app.route('/edit_file', methods=['POST'])
def edit_file():
    data = request.json
    old_name = data['old_name']
    new_name = data['new_name']
    content = data['content']
    path = data['path']

    # Logic to edit the file's name and content
    old_file_path = os.path.join(path, old_name)
    new_file_path = os.path.join(path, new_name)

    try:
        # Write new content to the new file
        with open(new_file_path, 'w') as new_file:
            new_file.write(content)

        # Remove the old file if the name has changed
        if old_name != new_name:
            os.remove(old_file_path)

        return jsonify(success=True)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Get the updated user settings from the form
        username = request.form['username']
        email = request.form['email']

        # Update the current user's settings in the database
        current_user.username = username
        current_user.email = email
        
        db.session.commit()  # Commit the changes to the database
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))  # Redirect back to settings page

    # Render the settings form with the current user's data
    return render_template('settings.html', user=current_user)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))



def log_activity(user_id, action, file_name=None):
    new_log = ActivityLog(user_id=user_id, action=action, file_name=file_name)
    db.session.add(new_log)
    db.session.commit()




@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    app.logger.debug("Received upload request.")
    
    # Default path should be just 'uploads' instead of 'uploads/<user_defined_path>'
    path = request.form.get('path', '')  # Get the subdirectory from the request, default to empty string
    app.logger.debug(f"Upload path: {path}")

    # Construct the full upload path
    full_path = os.path.join(UPLOAD_FOLDER, path) if path else UPLOAD_FOLDER
    app.logger.debug(f"Full upload path: {full_path}")

    if 'files' not in request.files:
        app.logger.error("No files part in request.")
        return jsonify({'error': 'No files part'}), 400

    files = request.files.getlist('files')
    app.logger.debug(f"Files received: {[file.filename for file in files]}")

    if not files:
        app.logger.error("No selected files.")
        return jsonify({'error': 'No selected files'}), 400

    # Ensure the uploads directory exists
    os.makedirs(full_path, exist_ok=True)

    total_size_gb = 0
    uploaded_files = []

    for file in files:
        if file.filename == '':
            app.logger.error("No selected file.")
            return jsonify({'error': 'No selected file'}), 400

        file_path = os.path.join(full_path, file.filename)

        try:
            file.save(file_path)  # Save the file in the specified folder
            uploaded_files.append(file.filename)

            file_size_bytes = os.path.getsize(file_path)
            total_size_gb += file_size_bytes / (1024 ** 3)

            log_activity(current_user.id, 'uploaded', file.filename)

            new_file = File(user_id=current_user.id, filename=file.filename, size=file_size_bytes / (1024 ** 3))
            db.session.add(new_file)
        except Exception as e:
            app.logger.error(f'File {file.filename} could not be saved: {str(e)}')
            return jsonify({'error': f'File {file.filename} could not be saved: {str(e)}'}), 500

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Could not save file information: {str(e)}')
        return jsonify({'error': f'Could not save file information: {str(e)}'}), 500

    return jsonify({'message': 'Files uploaded successfully', 'total_size_gb': total_size_gb}), 200




@app.route('/files', methods=['GET'])
def list_files():
    path = request.args.get('path', '')  # Get the path from query parameters
    full_path = os.path.join(UPLOAD_FOLDER, path)  # Construct the full path

    # Ensure the path is valid and inside the base directory
    if not os.path.commonpath([full_path, UPLOAD_FOLDER]) == UPLOAD_FOLDER:
        return jsonify({'error': 'Invalid path'}), 400

    try:
        items = []
        for entry in os.listdir(full_path):
            entry_path = os.path.join(full_path, entry)
            item = {
                'name': entry,
                'path': os.path.relpath(entry_path, UPLOAD_FOLDER),  # Relative path for easy access
                'type': 'folder' if os.path.isdir(entry_path) else 'file',
                'size': os.path.getsize(entry_path) if os.path.isfile(entry_path) else 0,
                'uploaded': os.path.getmtime(entry_path)  # Modify date as uploaded date
            }
            items.append(item)

        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/download_file', methods=['GET'])
def download_file():
    file_name = request.args.get('file')
    path = request.args.get('path')
    return send_from_directory(os.path.join(UPLOAD_FOLDER, path), file_name)


@app.route('/delete_file', methods=['POST'])
def delete_file():
    data = request.get_json()
    file_name = data['file_name']
    path = data['path']
    file_path = os.path.join(UPLOAD_FOLDER, path, file_name)
    os.remove(file_path)  # Delete the file
    return jsonify({'message': 'File deleted successfully'}), 200






@app.route('/activity-log', methods=['GET'])
@login_required
def get_activity_log():
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    return jsonify([{
        'user_id': log.user_id,
        'action': log.action,
        'file_name': log.file_name,
        'timestamp': log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    } for log in logs])




@app.route('/storage_plans', methods=['GET'])
def list_storage_plans():
    plans = StoragePlan.query.all()
    return jsonify([{'id': plan.id, 'name': plan.name, 'price': plan.price, 'storage_limit': plan.storage_limit} for plan in plans]), 200


@app.route('/set_storage_plan', methods=['POST'])
@login_required
def set_storage_plan():
    data = request.get_json()
    user = User.query.get(current_user.id)
    user.storage_plan_id = data['plan_id']
    db.session.commit()
    return jsonify({'message': 'Storage plan updated successfully'}), 200


@app.route('/storage_usage', methods=['GET'])
@login_required
def storage_usage():
    user = User.query.get(current_user.id)
    total_storage = user.storage_limit  # Get the storage limit from the user directly
    
    # Calculate used storage from the File model (size in GB)
    used_storage = sum(file.size for file in File.query.filter_by(user_id=current_user.id).all())

    remaining_storage = total_storage - used_storage

    return jsonify({
        'used_storage': used_storage,
        'remaining_storage': remaining_storage,
        'total_storage': total_storage
    }), 200





@app.route('/check_storage_limit', methods=['GET'])
@login_required
def check_storage_limit():
    user = User.query.get(current_user.id)
    storage_plan = StoragePlan.query.get(user.storage_plan_id)
    
    used_storage = sum(file.size for file in File.query.filter_by(user_id=current_user.id).all())
    
    if used_storage >= storage_plan.storage_limit:  # Assuming size is in GB
        return jsonify({'message': 'You have reached your storage limit. Consider upgrading your plan!'}), 200
    return jsonify({'message': 'You have sufficient storage available.'}), 200



@app.route('/plans')
def plans():
    plans = StoragePlan.query.all()  # Get all storage plans
    return render_template('plans.html', plans=plans)


@app.route('/api/balance', methods=['GET'])
@login_required
def get_balance():
    user = User.query.get(current_user.id)
    return jsonify({'balance': user.balance}), 200


@app.route('/upgrade_plan/<int:plan_id>', methods=['POST'])
@login_required
def upgrade_plan(plan_id):
    new_plan = StoragePlan.query.get(plan_id)

    if new_plan is None:
        flash('Selected plan does not exist.', 'danger')
        return redirect(url_for('dashboard'))

    # Check if the user has enough balance to upgrade
    if current_user.balance < new_plan.price:
        flash('Insufficient balance to upgrade the plan.', 'danger')
        return redirect(url_for('dashboard'))

    # Deduct the plan price from the user's balance
    current_user.balance -= new_plan.price
    current_user.storage_plan_id = new_plan.id
    current_user.storage_limit = new_plan.storage_limit  # Update storage limit based on the new plan
    db.session.commit()

    flash(f'You have successfully upgraded to {new_plan.name}!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/files/<filename>', methods=['GET'])
def get_file(filename):
    path = request.args.get('path')  # Get the path from the query string
    file_path = os.path.join(path, filename)

    if not os.path.isfile(file_path):
        return jsonify(error='File not found'), 404

    try:
        with open(file_path, 'r') as file:
            content = file.read()
        return content
    except Exception as e:
        return jsonify(error=str(e)), 500





if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
