// Firebase configuration and initialization
const firebaseConfig = {
  apiKey: "AIzaSyAH93_zyEiU4x_mOEFv9_voOiaCdG5tK5A",
  authDomain: "zatechdatabase.firebaseapp.com",
  projectId: "zatechdatabase",
  storageBucket: "zatechdatabase.firebasestorage.app",
  messagingSenderId: "599097664319",
  appId: "1:599097664319:web:c9dc57a7a78fc00e9d698a",
  measurementId: "G-W24TCYGZ3G"
};

// Initialize Firebase if not initialized
if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
}

// Auth instance for use in other files
const firebaseAuth = firebase.auth();
