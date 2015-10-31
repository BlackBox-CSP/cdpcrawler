try:
    import paramiko
except:
    print '[!] Looks like you are missing the paramiko library.  run \'pip install paramiko\''
    if os.name == 'nt':
        print '[!] *NOTE* you must install the Microsoft Visual C++ Compiler for Python 2.7 ' \
              'before installing paramiko.\r\n'\
              'This can be found at http://www.microsoft.com/en-us/download/details.aspx?id=44266'
import time
import getopt
import sys
import os
import re
import socket

#help message
def helpmsg():
    print 'Usage: cdpscanner.py [Options]' \
          '  Note: All options are optional.  User is prompted or defaults are used.' \
          '  -h or --help:  This help screen\n' \
          '  -i or --inputfile: specifies a file containing hosts to connect to.\n' \
          '  -u or --username: specifies a username to use\n' \
          '  -p or --password: Specifies the password to use\n' \
          '  -c or --commands: Specifies a list of commands to send\n' \
          '  -v or --verbose: Enables verbose output\n'\
          '  -t or --disable-telnet:  Disables fallback to telnet\n' \
          '  -d or --directory: Specifies a a directory to place the output files into\n'\
          '  --inventory:  Prints the inventory of all of the devices at the end\n'

#Command line argument parser
def cli_parser():
    global username
    global password
    global commands
    global working_directory
    global verbose_mode
    global telnet_disabled
    global host_set
    global inventory_enabled
    import getpass
    try:
        opts, args = getopt.getopt(sys.argv[1:],"i:u:p:c:hd:vt",["input=", "user=", "password=", "commands=",
                                                                 "directory=","verbose","disable-telnet","inventory"])
    except getopt.GetoptError:
        helpmsg()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            helpmsg()
            sys.exit()
        elif opt in ('-i', '--input'):
            inputfile = arg
            with open(org_dir+'/'+inputfile, 'rb') as hostfile:
                for device in hostfile:
                    try:
                        socket.inet_aton(device)
                        host_set.add(device)
                    except:
                        try:
                            dns_name,empty,ip_from_host = socket.gethostbyaddr(device.rstrip('\r\n'))
                            host_set.add(ip_from_host[0])
                        except socket.gaierror:
                            print "%s is not a valid host name or IP address" % device
                        except socket.herror:
                            print "%s is not a valid host name or IP address" % device
        elif opt in ('-t', '--disable-telnet'):
            telnet_disabled = True
        elif opt in ('-v', '--verbose'):
            verbose_mode = True
        elif opt in ('-u', '--user'):
            username = arg
        elif opt in ('-p', '--password'):
            password = arg
        elif opt in ('--inventory'):
            inventory_enabled = True
        elif opt in ('-c', '--commands'):
            commands = []
            try:
                with open(org_dir+'/'+arg, 'rb') as commandfile:
                    for line in commandfile:
                        commands.append(line.strip('\r\n'))
            except Exception as e:
                helpmsg()
                print e
                sys.exit()
    for opt, arg in opts:
        if opt in ('-d', '--directory'):
            working_directory = arg
            try:
                os.chdir(working_directory)
            except Exception as e:
                helpmsg()
                print e
                sys.exit()
    #Set list of IP addreses to connect to if the -i input file is not used
    if host_set == []:
        host_set.append(raw_input("Enter Switch Hostname or IP Address: ").upper())
    if username == '':
        username = raw_input("Enter Username: ")
    if password == '':
         password = getpass.getpass()



def telnet_getinfo(username,password, host, commands):
    import telnetlib
    outputfile = str(host)+ '.txt'
    tn = telnetlib.Telnet(host)
    print "telnet connection established to %s" % host
    tn.expect(['((\r*\n)+User Access Verification(\r*\n)+)*[Uu]sername: '],timeout=5)
    tn.write(username + '\r\n')
    tn.expect(['[Pp]assword: '])
    tn.write(password + '\r\n')
    enable_prompt = tn.expect([r'>$'],timeout=1)
    if enable_prompt[1] == None:
        pass
    else:
        tn.write('enable\r\n'+password+'\r\n')
    tn.write('terminal length 0\r\n')
    for command in commands:
        tn.write(command + '\r\n')
    tn.write('exit\r\n')
    output = tn.read_all()
    with open(outputfile, 'wb') as outfile:
        outfile.write(output)
    if verbose_mode == True:
        print output
    tn.close()
    return output
def ssh_getinfo(username,password,host,commands):
    def disable_paging(remote_conn):
        '''Disable paging on a Cisco device'''
        remote_conn.send("terminal length 0\n")
        time.sleep(1)
        # Clear the buffer on the screen
        output = remote_conn.recv(1000)
        return output
    print "Connecting to " + host + "\r\n"
    # Create instance of SSHClient object
    remote_conn_pre = paramiko.SSHClient()
    # Automatically add untrusted hosts (make sure okay for security policy in your environment)
    remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # initiate SSH connection
    remote_conn_pre.connect(host, username=username, password=password,timeout=TIMEOUT)
    print "SSH connection established to %s" % host
    # Use invoke_shell to establish an 'interactive session'
    remote_conn = remote_conn_pre.invoke_shell()
    print "Interactive SSH session established"
    # Strip the initial router prompt
    output = remote_conn.recv(1000)
    # See what we have
    if verbose_mode == True:
        print output
    # Turn off paging
    disable_paging(remote_conn)
    # Now let's try to send the router a command
    remote_conn.send("\n")
    for command in commands:
        remote_conn.send(command+'\n')
    # Wait for the command to complete
    time.sleep(3)
    output = remote_conn.recv(10000)
    if verbose_mode == True:
        print output
    with open(host+'.txt','w') as outputfile:
        for line in output:
            outputfile.write(line)
    return output
def output_parse(output):
    global host_set
    global seen_before
    global inventory
    matches = re.findall(r'Device ID: (\S+)\r*\nIP address: (\S+)\r*\nPlatform: cisco (WS-\S+,)',device_output)
    for match in matches:
        inventory.add(matches)
        if match[1] not in seen_before:
            host_set.add(match[1])
            seen_before.add(match[1])

if __name__ == '__main__':
    #Declaration of global variables
    inputfile = None
    host_set = set()
    username = ''
    password = ''
    commands = []
    failed_hosts = set()
    TIMEOUT = 30
    org_dir = os.curdir
    working_directory = os.curdir
    verbose_mode = False
    telnet_disabled = False
    current_set = set(host_set)
    seen_before = set()
    device = []
    inventory = set()
    inventory_enabled = False

    # Default commamnds if none are specififed in the CLI arguments
    commands = ['show cdp neighbor detail',
                'show inventory']

    # Run CLI parser function to set variables altered from defaults by CLI arguments.
    cli_parser()
    # Create a working copy of the set that contains all of the hosts.

    # Create a loop to make crawler recursive
    while host_set != set([]):
        # iterate through the set of hosts
        for host in current_set:
                # remove the host you are going to connect to from the set.
            currenthost = host_set.pop()
            try:
                # Try SSH and if that fails try telnet.
                device_output = ssh_getinfo(username,password,currenthost,commands).split('\r\n')
                # Check output for new hostnames
                output_parse(device_output)
            except:
                if telnet_disabled is not True:
                    try:
                        device_output = telnet_getinfo(username,password,currenthost,commands)
                        output_parse(device_output)
                    except:
                        # If both ssh and telnet fail add to a failed_hosts list
                        failed_hosts.add(currenthost.upper())
                else:
                 # If both ssh fails and telnet is disabled add to a failed_hosts list
                    failed_hosts.add(currenthost.upper())
        # Update the current list with the most recent updated host_set.
        current_set = set(host_set)

    #After everything has been completed or removed
    if inventory_enabled == True:
        print inventory
    for line in failed_hosts:
        print '[!] %s failed both ssh and telnet' % line
