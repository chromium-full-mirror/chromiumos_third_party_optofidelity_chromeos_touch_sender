/*
Copyright (c) 2019, OptoFidelity OY

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    3. All advertising materials mentioning features or use of this software must display the following acknowledgement: This product includes software developed by the OptoFidelity OY.
    4. Neither the name of the OptoFidelity OY nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

var serverSocketId;
var clientSocketId; 

// When app is launched, open the window
chrome.app.runtime.onLaunched.addListener(function() {
    // Keep display on while running the app.
    chrome.power.requestKeepAwake('display');

    running = true;

    // Listen to messages coming from GUI javascript
    chrome.runtime.onMessage.addListener(messageReceived);

    chrome.app.window.create('window.html', {
        'state': "fullscreen"
    }, function(createdWindow) {
        createdWindow.onClosed.addListener(function() {
            chrome.sockets.tcpServer.onAccept.removeListener(onAccept);
            chrome.sockets.tcp.onReceive.removeListener(onReceive);
            chrome.sockets.tcp.onReceiveError.removeListener(onReceiveError);
            chrome.runtime.onMessage.removeListener(messageReceived);
            send_tcp_msg('stop', close_tcpServer);
        });
    });
    
    // After launching the window, start TCP-server
    chrome.sockets.tcpServer.create({}, function(createInfo) {
        listenAndAccept(createInfo.socketId);
    });
});

// Listen and accept local TCP-connections
function listenAndAccept(socketId) {
    chrome.sockets.tcpServer.listen(socketId,
        '127.0.0.1', 50008, function(resultCode) {
        onListenCallback(socketId, resultCode)
    });
}

function onListenCallback(socketId, resultCode) {
    if (resultCode < 0) {
        console.log("Error listening:" + chrome.runtime.lastError.message);
        return;
    }
    serverSocketId = socketId;
    chrome.sockets.tcpServer.onAccept.addListener(onAccept)
}

function onAccept(info) {
    if (info.socketId != serverSocketId)
        return;
    clientSocketId = info.clientSocketId;
    
    // A new TCP connection has been established.
    chrome.sockets.tcp.send(info.clientSocketId, str2ab('OK;'),
        function(resultCode) {
        console.log("New TCP client connection accepted");
        chrome.runtime.sendMessage('device_conn', function(response) {});
    });

    send_tcp_msg('query_config');

    // Start receiving data.
    chrome.sockets.tcp.onReceive.addListener(onReceive);

    // Listen if the connection will break
    chrome.sockets.tcp.onReceiveError.addListener(onReceiveError);

    chrome.sockets.tcp.setPaused(info.clientSocketId, false);
}

function onReceive(recvInfo) {
    if (recvInfo.socketId != clientSocketId)
        return;

    var str_msg_arr = ab2str(recvInfo.data).split(";");
    str_msg_arr.forEach(function(str_msg){
        show_msg(str_msg);
    });
}

function onReceiveError(recvInfo) {
    if (recvInfo.socketId != clientSocketId)
        return;
    chrome.runtime.sendMessage('device_disconn', function(response) {});
}


function send_tcp_msg(msg, callback=function(){}) {
    if (typeof(clientSocketId) != "undefined"){
        chrome.sockets.tcp.getInfo(clientSocketId, function(info) {
            if (typeof(info) != "undefined"){
                if (info.connected){
                    chrome.sockets.tcp.send(clientSocketId, str2ab(msg + ';'), function(resultCode) {});
                }
            }
        });   
    }
    callback();
}

function close_tcpServer(){
    /*console.log('Closing TCP-connections')*/
    
    chrome.sockets.tcpServer.getSockets(function(socketInfos) {
        socketInfos.forEach(function(sock) {
            var sockId = sock.socketId;
            chrome.sockets.tcpServer.close(sockId, function(){
                close_tcpSockets();
            });
            /*console.log('Closed socket Server ' + sockId);*/
        });
    });
    /*console.log('Closed all TCP-connections');*/
}

function close_tcpSockets(){
    chrome.sockets.tcp.getSockets(function(socketInfos) {
        socketInfos.forEach(function(sock) {
            var sockId = sock.socketId;
            chrome.sockets.tcp.setPaused(sockId, true)
            chrome.sockets.tcp.close(sockId, function(){});
            /*console.log('Closed socket ' + sockId);*/
        });
    });
}

// Handle messages coming from GUI
function messageReceived(msg) {
    if (msg === 'stop') { 

        chrome.power.releaseKeepAwake();
        var wins = chrome.app.window.getAll();
        wins.forEach(function(win) {
            win.close();
        });
    }
    else if (msg === "pause") {
        send_tcp_msg(msg);
    }
    else if (msg === "reload") {
        chrome.runtime.reload();
    }
    else {
        send_tcp_msg(msg);
        /*chrome.sockets.tcp.send(clientSocketId, str2ab(msg + ';'),
            function(resultCode) {
        });*/
    }
}


// Helper functions, string-arraybuffer transforms

function str2ab(str) {
    var encoder = new TextEncoder('utf-8');
    return encoder.encode(str).buffer;
}

function ab2str(buf) {
    var decoder = new TextDecoder('utf-8');
    return decoder.decode(buf);
}

// Send message to frontpage javascript
function show_msg(msg) {
    chrome.runtime.sendMessage(msg, function(response) {
    });
}