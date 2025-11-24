#ifndef MEETINGSDK_HEADLESS_LINUX_SAMPLE_SOCKETSERVER_H
#define MEETINGSDK_HEADLESS_LINUX_SAMPLE_SOCKETSERVER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <signal.h>
#include <pthread.h>

#include <iostream>

#include "Singleton.h"
#include "Log.h"

using namespace std;


class SocketServer : public Singleton<SocketServer> {
    friend class Singleton<SocketServer>;

    const string c_socketPath = "/tmp/audio/meeting.sock";
    const int c_bufferSize = 256;

    struct sockaddr_un m_addr;

    int m_listenSocket = 0;
    int m_dataSocket = 0;

    pthread_t m_pid = 0;
    pthread_mutex_t m_mutex;

    bool ready = false;
    bool m_clientConnected = false;

    void* run();
    static void* threadCreate(void* obj);
    static void threadKill(int sig, siginfo_t* info, void* ctx);

public:
    SocketServer();
    ~SocketServer();
    int start();
    void stop();

    int writeBuf(const unsigned char* buf, int len);
    int writeBuf(const char* buf, int len);
    int writeStr(const string& str);

    bool isReady();
    bool hasClient();

    void cleanup();
};

#endif //MEETINGSDK_HEADLESS_LINUX_SAMPLE_SOCKETSERVER_H