// Handle logout
document.addEventListener('DOMContentLoaded', () => {
    const logoutForm = document.querySelector('form[action="/admin/logout"]');
    
    if (logoutForm) {
        logoutForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            try {
                // Sign out from Firebase
                await firebaseAuth.signOut();
                
                // Clear server-side session
                logoutForm.submit();

            } catch (error) {
                console.error('Logout error:', error);
                logoutForm.submit();
            }
        });
    }
});
