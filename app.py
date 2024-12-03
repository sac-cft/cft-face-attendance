from flask import Flask, request, jsonify
from PIL import Image
import boto3
import io
from pymongo import MongoClient
from datetime import datetime
import pytz

# Initialize Flask App
app = Flask(__name__)

# Initialize AWS Rekognition and DynamoDB clients
rekognition = boto3.client('rekognition', region_name='us-east-1')
dynamodb = boto3.client('dynamodb', region_name='us-east-1')

# MongoDB Client Setup
client = MongoClient("mongodb+srv://SAC:ZRb7i1FdJ7eC3SUp@cluster0.btu1pyt.mongodb.net")  # Adjust MongoDB URI if needed
db = client['face_recognition']  # Database
users_collection = db['users']  # Collection

@app.route("/api/get-face-name/", methods=["POST"])
def get_face_name():
    # Get the image file from the request
    user_image = request.files.get('userImage')
    action = request.form.get('selected')  # This can be either 'checkin' or 'checkout'

    if user_image is None:
        return jsonify({"error": "No image provided"}), 400

    if action not in ['checkin', 'checkout']:
        return jsonify({"error": "Invalid action. Use 'checkin' or 'checkout'."}), 400

    try:
        # Log the received image
        print(f"Received image: {user_image.filename}")

        # Open the image using PIL
        image = Image.open(user_image)
        print("Image opened successfully.")

        stream = io.BytesIO()
        image.save(stream, format="JPEG")
        image_binary = stream.getvalue()

        # Send the image to AWS Rekognition for face recognition
        response = rekognition.search_faces_by_image(
            CollectionId='famouspersons',
            Image={'Bytes': image_binary}
        )

        # Log the response from Rekognition
        print("Rekognition Success")

        found = False
        user_details = {}

        for match in response.get('FaceMatches', []):
            face_id = match['Face']['FaceId']
            confidence = match['Face']['Confidence']

            # Log the face ID and confidence
            print(f"Found face ID: {face_id} with confidence: {confidence}")

            # Fetch user data from DynamoDB
            face = dynamodb.get_item(
                TableName='face_recognition',
                Key={'RekognitionId': {'S': face_id}}
            )

            if 'Item' in face:
                user_details = face['Item']
                print('User details:', user_details)
                found = True
                break

        if found:
            # Extract user details from DynamoDB response
            rekognition_id = user_details.get('RekognitionId', {}).get('S')
            user_id = user_details.get('UserId', {}).get('S')
            full_name = user_details.get('FullName', {}).get('S')

            # Get current timestamp in IST (Indian Standard Time)
            tz = pytz.timezone('Asia/Kolkata')
            current_time = datetime.now(tz)

            # Handle Check-in/Check-out logic
            if action == 'checkin':
                # If user is checking in
                update_data = {'checkinTime': current_time.strftime('%Y-%m-%d %H:%M:%S')}
                # Assume that you are storing the user data with check-in time
                users_collection.update_one({"userId": user_id}, {"$set": update_data}, upsert=True)
                return jsonify({
                    "message": f"Check-in successful for {full_name}",
                    "user_details": user_details
                }), 200

            elif action == 'checkout':
                # If user is checking out
                # Assume you have logic to calculate checkout eligibility based on check-in time
                update_data = {'checkoutTime': current_time.strftime('%Y-%m-%d %H:%M:%S')}
                # Updating checkout time in the database
                users_collection.update_one({"userId": user_id}, {"$set": update_data})
                return jsonify({
                    "message": f"Check-out successful for {full_name}",
                    "user_details": user_details
                }), 200

        else:
            # If the person is not found
            print('Person cannot be recognized')
            return jsonify({"message": "Please register yourself and try again."}), 200

    except Exception as e:
        print("Error: ", str(e))  # Log the error
        return jsonify({"error": str(e)}), 500


# Remove app.run() and prepare for deployment with Gunicorn
if __name__ == "__main__":
    # Flask app will be served using Gunicorn instead of app.run() in production
    pass