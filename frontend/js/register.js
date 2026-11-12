const form =
    document.getElementById(
        "registerForm"
    );
const message =
    document.getElementById(
        "message"
    );
form.addEventListener(
    "submit",
    async event => {
        event.preventDefault();
        const name =
            document.getElementById(
                "name"
            ).value;
        const image =
            document.getElementById(
                "image"
            ).files[0];
        if (!image) {
            return;
        }
        const formData =
            new FormData();
        formData.append(
            "name",
            name
        );
        formData.append(
            "file",
            image
        );
        message.innerText =
            "Đang xử lý...";
        try {
            const response =
                await fetch(
                    "/api/register",
                    {
                        method: "POST",
                        body: formData
                    }
                );
            const data =
                await response.json();
            if (data.success) {
                message.innerText =
                    data.message;
                form.reset();
                loadUsers();
            } else {
                message.innerText =
                    "Lỗi: " +
                    data.message;
            }
        } catch (error) {
            message.innerText =
                "Không thể kết nối server.";
            console.error(error);
        }
    }
);
document.addEventListener("DOMContentLoaded", () => {
    loadUsers();
    initModalEvents();
});
// =========================================================
// LOAD USER LIST & RENDER
// =========================================================
async function loadUsers() {
    const userListUl = document.getElementById("userList");
    if (!userListUl) return;
    try {
        const response = await fetch("/api/users");
        const users = await response.json();
        userListUl.innerHTML = "";
        if (users.length === 0) {
            userListUl.innerHTML = "<li>Chưa có người dùng nào.</li>";
            return;
        }
        users.forEach(user => {
            const li = document.createElement("li");
            li.style.cssText = "padding: 8px; border-bottom: 1px solid #ccc; display: flex; align-items: center; justify-content: space-between;";
            const avatarSrc = user.avatar_url || 'https://res.cloudinary.com/dnnfx0sqr/image/upload/v1789444512/23b69385-27fb-4457-bce2-3d217912017c.png';
            li.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px; cursor: pointer;" onclick="openUserModal(${user.id}, '${user.name}', '${avatarSrc}')">
                    <img src="${avatarSrc}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover;">
                    <span>${user.name}</span>
                </div>
                <div>
                    <button onclick="removeUser(${user.id}, '${user.name}')" style="background: #ff4d4f; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer;">
                        Xóa
                    </button>
                </div>
            `;
            userListUl.appendChild(li);
        });
    } catch (error) {
        console.error("Lỗi khi tải danh sách:", error);
    }
}
// =========================================================
// DELETE USER
// =========================================================
async function removeUser(userId, userName) {
    if (!confirm(`Bạn có chắc chắn muốn xóa "${userName}"?`)) return;
    try {
        const response = await fetch(`/api/users/${userId}`, { method: "DELETE" });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            loadUsers();
        } else {
            alert("Lỗi: " + data.message);
        }
    } catch (error) {
        alert("Không thể kết nối tới máy chủ.");
        console.error(error);
    }
}
// =========================================================
// MODAL DETAIL & EDIT USER
// =========================================================
function initModalEvents() {
    // Tự động inject HTML Modal vào body nếu chưa có
    if (!document.getElementById("userModal")) {
        const modalHTML = `
        <div id="userModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); justify-content:center; align-items:center; z-index:1000;">
            <div style="background:#fff; padding:20px; border-radius:8px; width:350px; text-align:center; position:relative;">
                <span id="closeModal" style="position:absolute; top:10px; right:15px; cursor:pointer; font-size:20px; font-weight:bold;">&times;</span>
                <!-- Hiển thị Avatar Phóng To -->
                <img id="modalAvatar" src="" style="width:180px; height:180px; border-radius:8px; object-fit:cover; margin-bottom:15px; border:1px solid #ddd;">
                <!-- Form Chỉnh sửa -->
                <form id="editUserForm" style="display:flex; flex-direction:column; gap:10px; text-align:left;">
                    <input type="hidden" id="editUserId">
                    <label><strong>Tên người dùng:</strong></label>
                    <input type="text" id="editUserName" required style="padding:6px; border:1px solid #ccc; border-radius:4px;">
                    <label><strong>Đổi ảnh đại diện mới (Không bắt buộc):</strong></label>
                    <input type="file" id="editUserImage" accept="image/*" style="padding:4px;">
                    <button type="submit" style="background:#52c41a; color:white; border:none; padding:8px; border-radius:4px; cursor:pointer; margin-top:10px; font-weight:bold;">
                        Lưu Thay Đổi
                    </button>
                </form>
                <p id="modalMessage" style="margin-top:10px; font-size:14px;"></p>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }
    const modal = document.getElementById("userModal");
    const closeModal = document.getElementById("closeModal");
    const editForm = document.getElementById("editUserForm");
    closeModal.onclick = () => { modal.style.display = "none"; };
    window.onclick = (event) => { if (event.target === modal) modal.style.display = "none"; };
    // Xử lý gửi Form Cập nhật
    editForm.onsubmit = async (e) => {
        e.preventDefault();
        const userId = document.getElementById("editUserId").value;
        const name = document.getElementById("editUserName").value;
        const imageFile = document.getElementById("editUserImage").files[0];
        const modalMsg = document.getElementById("modalMessage");
        const formData = new FormData();
        formData.append("name", name);
        if (imageFile) {
            formData.append("file", imageFile);
        }
        modalMsg.style.color = "blue";
        modalMsg.innerText = "Đang cập nhật...";
        try {
            const response = await fetch(`/api/users/${userId}`, {
                method: "PUT",
                body: formData
            });
            const data = await response.json();
            if (data.success) {
                modalMsg.style.color = "green";
                modalMsg.innerText = "Cập nhật thành công!";
                setTimeout(() => {
                    modal.style.display = "none";
                    loadUsers();
                }, 1000);
            } else {
                modalMsg.style.color = "red";
                modalMsg.innerText = "Lỗi: " + data.message;
            }
        } catch (error) {
            modalMsg.style.color = "red";
            modalMsg.innerText = "Lỗi kết nối máy chủ.";
            console.error(error);
        }
    };
}
// Hàm mở Modal và nạp dữ liệu
function openUserModal(id, name, avatarUrl) {
    document.getElementById("editUserId").value = id;
    document.getElementById("editUserName").value = name;
    document.getElementById("modalAvatar").src = avatarUrl;
    document.getElementById("editUserImage").value = ""; 
    document.getElementById("modalMessage").innerText = "";
    document.getElementById("userModal").style.display = "flex";
}