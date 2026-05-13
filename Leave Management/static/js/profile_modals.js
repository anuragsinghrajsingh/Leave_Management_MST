document.addEventListener("DOMContentLoaded", function()
        {
            function openModalElement(modalId, beforeOpen)
            {
                const modal = document.getElementById(modalId);
                if (!modal) return;

                if (typeof beforeOpen === "function")
                {
                    beforeOpen();
                }

                modal.style.display = "flex";
                document.body.style.overflow = "hidden";
            }

            function closeModalElement(modalId, afterClose)
            {
                const modal = document.getElementById(modalId);
                if (!modal) return;

                modal.style.display = "none";

                if (typeof afterClose === "function")
                {
                    afterClose();
                }

                document.body.style.overflow = "";
            }

            const passwordTrigger = document.getElementById("profilePasswordTrigger");
            const mastheadAvatarCard = document.getElementById("mastheadAvatarCard");
            const viewPhotoTrigger = document.getElementById("profileViewPhotoTrigger");
            const editPhotoTrigger = document.getElementById("profileEditPhotoTrigger");

            const viewPhotoClose = document.getElementById("viewPhotoModalClose");
            const editPhotoClose = document.getElementById("editPhotoModalClose");
            const passwordClose = document.getElementById("passwordModalClose");

            if (passwordTrigger)
            {
                passwordTrigger.addEventListener("click", function(event)
                {
                    event.preventDefault();
                    event.stopPropagation();
                    if (typeof openPasswordModal === "function")
                    {
                        openPasswordModal();
                    }
                    else
                    {
                        openModalElement("passwordModal");
                    }
                });
            }

            if (mastheadAvatarCard && viewPhotoTrigger && editPhotoTrigger)
            {
                const showAvatarChange = function()
                {
                    mastheadAvatarCard.classList.add("show-edit-overlay");
                };

                const hideAvatarChange = function()
                {
                    mastheadAvatarCard.classList.remove("show-edit-overlay");
                };

                viewPhotoTrigger.addEventListener("click", function(event)
                {
                    event.preventDefault();
                    event.stopPropagation();

                    if (!mastheadAvatarCard.classList.contains("show-edit-overlay"))
                    {
                        showAvatarChange();
                        return;
                    }

                    hideAvatarChange();
                    openModalElement("viewPhotoModal");
                });

                editPhotoTrigger.addEventListener("click", function(event)
                {
                    event.preventDefault();
                    event.stopPropagation();
                    showAvatarChange();
                    openModalElement("editPhotoModal", function()
                    {
                        if (typeof resetEditor === "function")
                        {
                            resetEditor();
                        }

                        const photoError = document.getElementById("photoError");
                        const uploadArea = document.getElementById("uploadArea");

                        if (photoError) photoError.classList.add("hidden");
                        if (uploadArea) uploadArea.classList.remove("error");
                    });
                });

                editPhotoTrigger.addEventListener("keydown", function(event)
                {
                    if (event.key === "Enter" || event.key === " ")
                    {
                        event.preventDefault();
                        showAvatarChange();
                        openModalElement("editPhotoModal", function()
                        {
                            if (typeof resetEditor === "function")
                            {
                                resetEditor();
                            }
                        });
                    }
                });

                document.addEventListener("click", function(event)
                {
                    if (!mastheadAvatarCard.contains(event.target))
                    {
                        hideAvatarChange();
                    }
                });
            }

            if (viewPhotoClose)
            {
                viewPhotoClose.addEventListener("click", function(event)
                {
                    event.preventDefault();
                    event.stopPropagation();
                    closeModalElement("viewPhotoModal");
                });
            }

            if (editPhotoClose)
            {
                editPhotoClose.addEventListener("click", function(event)
                {
                    event.preventDefault();
                    event.stopPropagation();
                    closeModalElement("editPhotoModal", function()
                    {
                        if (typeof resetEditor === "function")
                        {
                            resetEditor();
                        }
                    });
                });
            }

            if (passwordClose)
            {
                passwordClose.addEventListener("click", function(event)
                {
                    event.preventDefault();
                    event.stopPropagation();
                    if (typeof closePasswordModal === "function")
                    {
                        closePasswordModal();
                    }
                    else
                    {
                        closeModalElement("passwordModal");
                    }
                });
            }
        });
