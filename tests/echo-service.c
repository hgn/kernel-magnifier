#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <pthread.h>

#define PORT 12345
#define MAX_CONNECTIONS 5

void *handle_client(void *arg) {
    int client_socket = *(int *)arg;
    char buffer[1024];
    ssize_t bytes_received;

    struct sockaddr_storage client_info;
    socklen_t addr_len = sizeof(client_info);

    // Get the client's IP address and port
    if (getpeername(client_socket, (struct sockaddr *)&client_info, &addr_len) == 0) {
        char client_ip[INET6_ADDRSTRLEN];
        int client_port;

        if (client_info.ss_family == AF_INET) {
            struct sockaddr_in *ipv4 = (struct sockaddr_in *)&client_info;
            inet_ntop(AF_INET, &ipv4->sin_addr, client_ip, INET6_ADDRSTRLEN);
            client_port = ntohs(ipv4->sin_port);
        } else if (client_info.ss_family == AF_INET6) {
            struct sockaddr_in6 *ipv6 = (struct sockaddr_in6 *)&client_info;
            inet_ntop(AF_INET6, &ipv6->sin6_addr, client_ip, INET6_ADDRSTRLEN);
            client_port = ntohs(ipv6->sin6_port);
        } else {
            strcpy(client_ip, "Unknown");
            client_port = -1;
        }

        printf("Client connected from %s:%d\n", client_ip, client_port);
    }

    while ((bytes_received = recv(client_socket, buffer, sizeof(buffer), 0)) > 0) {
        send(client_socket, buffer, bytes_received, 0);
    }

    close(client_socket);
    pthread_exit(NULL);
}

int main() {
    int server_socket, client_socket;
    struct sockaddr_storage server_addr, client_addr;
    socklen_t client_addr_len = sizeof(client_addr);
    pthread_t thread_id;

    // Create socket
    server_socket = socket(AF_INET6, SOCK_STREAM, 0);
    if (server_socket == -1) {
        perror("Error creating socket");
        exit(1);
    }

    // Bind
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.ss_family = AF_INET6;
    ((struct sockaddr_in6 *)&server_addr)->sin6_port = htons(PORT);
    ((struct sockaddr_in6 *)&server_addr)->sin6_addr = in6addr_any;

    if (bind(server_socket, (struct sockaddr *)&server_addr, sizeof(server_addr)) == -1) {
        perror("Error binding");
        exit(1);
    }

    // Listen
    if (listen(server_socket, MAX_CONNECTIONS) == -1) {
        perror("Error listening");
        exit(1);
    }

    printf("Server is listening on port %d...\n", PORT);

    // Accept and handle incoming connections
    while (1) {
        client_socket = accept(server_socket, (struct sockaddr *)&client_addr, &client_addr_len);
        if (client_socket == -1) {
            perror("Error accepting connection");
            continue;
        }

        if (pthread_create(&thread_id, NULL, handle_client, &client_socket) != 0) {
            perror("Error creating thread");
            continue;
        }

        pthread_detach(thread_id);
    }

    close(server_socket);
    return 0;
}
