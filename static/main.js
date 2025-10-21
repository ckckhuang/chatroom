
var socket = io();
socket.on('load_history', function(msgs){
    const chat = document.getElementById('chat');
    chat.innerHTML = '';
    msgs.forEach(m => chat.innerHTML += `<div>${m.username}: ${m.message}</div>`);
});

socket.on('receive_message', function(m){
    const chat = document.getElementById('chat');
    chat.innerHTML += `<div>${m.username}: ${m.message}</div>`;
});

function sendMessage(){
    const input = document.getElementById('msg');
    socket.emit('send_message', {username: "{{ nickname }}", message: input.value, reply_to_id: null});
    input.value = '';
}
