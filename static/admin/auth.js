// Handles admin login using Firebase Authentication (AI was used to help write this file).

// Use shared Firebase Auth instance
const auth = firebaseAuth

// Get elements
const loginForm = document.getElementById('login-form');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');
const loginButton = document.getElementById('login-button');
const errorDiv = document.getElementById('error');

function showError(message){
    errorDiv.textContent = message;
    errorDiv.classList.add('show');
    setTimeout(() => errorDiv.classList.remove('show'), 5000);
}

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    loginButton.disabled = true;
    loginButton.textContent = 'Logging in...';
    errorDiv.classList.remove('show');

    try{
        // Authenticate with Firebase
        const userCredential = await auth.signInWithEmailAndPassword(email, password);
        const idToken = await userCredential.user.getIdToken();

        // Send token to backend to set secure cookie
        const response = await fetch('/admin/auth/set-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: idToken })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Authentication failed');
        }

        // Redirect to admin dashboard
        window.location.href = '/admin';

    } catch (error) {

        let message = 'Login failed. Please try again.';

        if (error.code) {
            // Handle Firebase auth errors
            switch (error.code) {
                case 'auth/invalid-email':
                    message = 'Invalid email address.';
                    break;
                case 'auth/user-not-found':
                case 'auth/wrong-password':
                case 'auth/invalid-credential':
                    message = 'Incorrect email or password.';
                    break;
                case 'auth/too-many-requests':
                    message = 'Too many failed login attempts. Please try again later.';
                    break;
                case 'auth/user-disabled':
                    message = 'This account has been disabled.';
                    break;
                case 'auth/network-request-failed':
                    message = 'Network error. Please check your connection.';
                    break;
            }
        }   

        // Server errors
        else if (error.message) {
            message = error.message;
        }

        showError(message);
        loginButton.disabled = false;
        loginButton.textContent = 'Login';
    }
});

// Auto-logout on token expiration
auth.onAuthStateChanged((user) => {
    // Avoid redirect loop
    if (window.location.pathname === '/admin/login') {
        return
    }

    if (!user && window.location.pathname.startsWith('/admin')) {
        window.location.href = '/admin/login';
    }
});
