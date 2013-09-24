"""simple-check

This is intended to be a very simple python NNTP nzb checking application that
can be fully implemented within a single python file.
"""

import argparse
import glob
import re
import socket
import ssl
import sys

# Begin configuration area

server = 'news.example.com'
port = 119
username = 'username'
password = 'password'
use_ssl = False

# End configuration area


def ParseResponse(data):
    """Parse response from server.

    Pass in a single line from the server and it will be broken into its
    component parts (if it is formatted properly). Both the server code as well
    as the string from the response will be returned to the caller.

    If the format is not recognized None will be returned.
    """

    # break apart the response code and (optionally) the rest of the line
    match = re.match(r'(\d+)(?: (.*))?\r\n', data)
    if match:
        return match.group(1), match.group(2)
    return None


def GetServerResponse(s):
    """ Get server response.

    Get the response to a command send to the NNTP server and return it for use
    by the calling function.
    """

    # receive server response
    data = s.recv(1024)

    # parse server response
    code, text = ParseResponse(data)

    return code, text


def SendServerCommand(s, command):
    """ Send a command to the server and get the response.

    Send the command out to the server and pass the response back to the calling
    function.
    """

    # send the command to the server
    s.sendall(command)

    # get the response from the server
    code, text = GetServerResponse(s)

    return code, text


def Connect(server, port=119, use_ssl=False):
    """Connect to NNTP server.

    Using the server address, port, and a flag to use ssl, we will connect to
    the server and parse the response from the server using standard sockets.
    """

    # create a socket object and connect
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if use_ssl:
        s = ssl.wrap_socket(s)
    s.connect((server, port))

    # get the servers connection string
    code, text = GetServerResponse(s)

    # check for success
    if code != '200':
        return None
    else:
        return s


def Login(s, username, password):
    """Login to server.

    Login to the server using a username and password. Check for failure to
    login and intelligently handle server responses.
    """

    # send the username to the server
    code, text = SendServerCommand(s, "AUTHINFO USER " + username + "\r\n")

    # get code 381 if a password is required
    if code != '381':
        return None

    # send the password to the server
    code, text = SendServerCommand(s, "AUTHINFO PASS " + password + "\r\n")

    # get code 281 if successfully logged in
    if code != '281':
        return None

    # all went well, return true
    return True


def Check(s, messageId):
    """Check a binary article.

    Make sure that we do get a 223 code back from the server.
    """

    # send the post command to the server
    code, text = SendServerCommand(s, "STAT " + messageId + "\r\n")

    # if we did not get code 223 article doesnt exist
    if code != '223':
        return False

    # article exists
    return True


if __name__ == '__main__':

    # argument parsing comes first
    parser = argparse.ArgumentParser(description="check for existence of nzb articles on usenet server")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    group.add_argument("-q", "--quiet", help="disable output", action="store_true")
    parser.add_argument("file", help="file(s) to post", nargs="+")
    parser.add_argument("--host", help="hostname of server")
    parser.add_argument("--port", help="port for posting server", type=int)
    parser.add_argument("--ssl", help="use ssl for connecting to server", action="store_true")
    parser.add_argument("--user", help="username for posting server")
    parser.add_argument("--pass", help="password for posting server")
    args = parser.parse_args()

    # override any passed values
    if args.host:
        server = args.host
    if args.port:
        port = args.port
    if args.ssl:
        use_ssl = True
    if args.user:
        username = args.user
    if getattr(args, 'pass'):
        password = getattr(args, 'pass')

    # holds our files
    files = []

    # expand any patterns pass as files
    for pattern in args.file:
        files += glob.glob(pattern)

        # connect to server
    conn = Connect(server, port, use_ssl)

    # check for failure
    if conn is None:
        print("Unable to connect to server.")
        sys.exit()

    # login to server
    if Login(conn, username, password) is None:
        print("Unable to login to server.")
        conn.close()
        sys.exit()

    # Do the nzb lookup.
    import xml.etree.ElementTree as ET

    # loop for each file
    for eachFile in files:
        tree = ET.parse(eachFile)
        root = tree.getroot()

        totalMissing = 0.0
        totalFound = 0.0

        for element in root:

            filename = element.get('subject')
            match = re.match(r'.*\"(.*)\".*', filename)
            print("new file - " + match.group(1))

            fileMissing = 0.0
            fileFound = 0.0

            segments = element.findall('.//{http://www.newzbin.com/DTD/2003/nzb}segment')
            for segment in segments:
                result = Check(conn, "<" + segment.text + ">")
                if result:
                    totalFound += 1
                    fileFound += 1
                    #print("    " + segment.text + " is found")
                else:
                    totalMissing += 1
                    fileMissing += 1
                    #print("    " + segment.text + " MISSING")

            # output file stats
            if fileMissing == 0:
                print("File percent available: 100%")
            else:
                print("File percent available: " + str(round((fileMissing / fileFound) * 100, 2)) + "%")
            print("\r\n")

        # output total nzb stats
        print("\r\n")
        if totalMissing == 0:
            print("Total percent available: 100%")
        else:
            print("Total percent available: " + str(round((totalMissing / totalFound) * 100, 2)) + "%")
        print("\r\n")

    # close the connection
    conn.close()