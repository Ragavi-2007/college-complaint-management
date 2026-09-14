document.addEventListener("DOMContentLoaded", function () {
    const photoInput = document.querySelector('input[name="photo"]');

    if (photoInput) {
        photoInput.addEventListener("change", function () {
            if (this.files.length > 0) {
                const file = this.files[0];
                const maxSize = 5 * 1024 * 1024;

                if (file.size > maxSize) {
                    alert("Photo must be 5 MB or smaller.");
                    this.value = "";
                }
            }
        });
    }
});
