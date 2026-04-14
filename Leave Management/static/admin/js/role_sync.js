document.addEventListener("DOMContentLoaded", function () 
{
    const userRole = document.getElementById("id_role");

    if (!userRole) return;

    function syncRole() 
    {
        const profileRoles = document.querySelectorAll('[name$="-role"]');

        profileRoles.forEach(field => 
        {
            field.value = userRole.value;
        });
    }

    syncRole();
    userRole.addEventListener("change", syncRole);
});


document.addEventListener("DOMContentLoaded", function () {

    function attachPreview(input) {

        input.addEventListener("change", function () {

            const file = input.files[0];
            if (!file) return;

            const reader = new FileReader();

            reader.onload = function (e) {

                let preview = input.parentElement.querySelector(".image-preview");

                // If preview doesn't exist → create
                if (!preview) {
                    preview = document.createElement("img");
                    preview.className = "image-preview";

                    preview.style.display = "block";
                    preview.style.marginTop = "10px";
                    preview.style.width = "120px";
                    preview.style.height = "120px";
                    preview.style.objectFit = "cover";
                    preview.style.borderRadius = "8px";
                    preview.style.border = "1px solid #ddd";

                    input.parentElement.appendChild(preview);
                }

                preview.src = e.target.result;
            };

            reader.readAsDataURL(file);
        });
    }

    // 🔥 find ALL file inputs (for inline also)
    const inputs = document.querySelectorAll("input[type='file']");

    inputs.forEach(input => attachPreview(input));

});