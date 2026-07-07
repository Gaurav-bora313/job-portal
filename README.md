# job-portal

Before running the applicaition in your system, please assure that you have flask and python-dotenv installed in your virtual environment. In order to do the same, please paste the following command after making the venv:
```pip install flask python-dotenv```

After cloning the repository, please make a .env file in your main project directory and define the following objects:
1. ADMIN_USERNAME
2. ADMIN_PASSWORD
3. FLASK_SECRET_KEY

Finally run the application. In order to access the admin portal, go to the admin route by typing in,
```localhost:5000/admin```

**Note** that this will ask for login credentials. Please enter the credentials which you earlier defined in your .env file
