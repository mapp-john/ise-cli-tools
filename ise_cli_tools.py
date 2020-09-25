import os,\
        re,\
        sys,\
        time,\
        yaml,\
        shutil,\
        socket,\
        random,\
        getpass,\
        logging,\
        netmiko,\
        traceback
from datetime import datetime
from threading import Thread
import queue as queue
from xftpd import ftp_server,\
                    sftp_server


#
#
#
# Define Password Function
def define_password():
    password = None
    while not password:
        password = getpass.getpass('Please Enter ISE CLI Password: ')
        passwordverify = getpass.getpass('Re-enter ISE CLI Password to Verify: ')
        if not password == passwordverify:
            print('Passwords Did Not Match Please Try Again')
            password = None
    return password

def COMMANDS(PAN_Dict,serverList,outputList,sftp_mode,FTP_ADDR,FTP_USER,FTP_PASS,FTP_PORT):
    while not serverList.empty():
        device = serverList.get_nowait()
        server = device['server']
        username = device['user']
        password = device['Pass']
        # Netmiko Device Type
        device_type = 'linux'

        try:

            # Connection Break
            counter = len(PAN_Dict)-serverList.qsize()
            print(f'\n[{counter}] Connecting to: {server}\n')
            outputList.put(f'\n[{counter}] Connecting to: {server}\n')
            # Connection Handler
            connection = netmiko.ConnectHandler(ip=server, device_type=device_type, username=username, password=password, global_delay_factor=6)

            # Enter App Config ISE
            output = connection.send_command('application config ise', expect_string=r'\[0\]Exit')
            ##TEST PRINT
            #print(output)
            output = connection.send_command('16', expect_string=r'\[0\]Exit')
            filename = re.search(r'FullReport.*\.csv',output).group()
            output = connection.send_command('0',expect_string=r'\#')

            # IF Statement for FTP vs SFTP
            if sftp_mode:
                output = connection.send_command(f'crypto host_key add host {FTP_ADDR}',expect_string=r'\#')
                if not re.search(fr'{FTP_ADDR} RSA .*',output):
                    print(f'\n!\n!\n[{counter}] SFTP RSA ERROR - {server}\nCrypto Host Key failure\n\n\n!')
                    outputList.put(f'\n!\n!\n[{counter}] SFTP RSA ERROR - {server}\nCrypto Host Key failure\n\n\n!')
                    connection.disconnect()
                    outputList.put(None)
                    return

                output = connection.send_command(f'copy disk:/{filename} sftp://{FTP_ADDR}/{server}',expect_string=r'Username\:')
                output = connection.send_command(f'{FTP_USER}',expect_string=r'Password\:')
                output = connection.send_command(f'{FTP_PASS}',expect_string=r'\#')
                if output.endswith('failed'):
                    print(f'\n!\n!\n[{counter}] FILE TRANSFER ERROR - {server}\nFile Transfer failure\n\n\n!')
                    outputList.put(f'\n!\n!\n[{counter}] FILE TRANSFER ERROR - {server}\nFile Transfer failure\n\n\n!')
                    connection.disconnect()
                    outputList.put(None)
                    return
                output = connection.send_command(f'delete disk:/{filename}',expect_string=r'\#')
            else:
                output = connection.send_command(f'copy disk:/{filename} ftp://{FTP_ADDR}:{FTP_PORT}/{server}',expect_string=r'Username\:')
                output = connection.send_command(f'{FTP_USER}',expect_string=r'Password\:')
                output = connection.send_command(f'{FTP_PASS}',expect_string=r'\#')
                if output.endswith('failed'):
                    print(f'\n!\n!\n[{counter}] FILE TRANSFER ERROR - {server}\nFile Transfer failure\n\n\n!')
                    outputList.put(f'\n!\n!\n[{counter}] FILE TRANSFER ERROR - {server}\nFile Transfer failure\n\n\n!')
                    connection.disconnect()
                    outputList.put(None)
                    return
                output = connection.send_command(f'delete disk:/{filename}',expect_string=r'\#')







            print(f'!\n[{counter}] ENDPOINT REPORT COMPLETED - {server}\n!')
            outputList.put(f'!\n[{counter}] ENDPOINT REPORT COMPLETED - {server}\n!')
            try:
                connection.disconnect()
            except OSError:
                pass
            except:
                print(f'\n!\n!\n[{counter}] DISCONNECT ERROR - {server}\n{traceback.format_exc()}\n\n\n!')
                outputList.put(f'\n!\n!\n[{counter}] DISCONNECT ERROR - {server}\n{traceback.format_exc()}\n\n\n!')

        except:    # exceptions as exceptionOccured:
            print(f'\n!\n!\n[{counter}] CONNECTION ERROR - {server}\n{traceback.format_exc()}\n\n\n!')
            outputList.put(f'\n!\n!\n[{counter}] CONNECTION ERROR - {server}\n{traceback.format_exc()}\n\n\n!')

    # Sending None to outputList as to delineate when a device has completed
    outputList.put(None)
    return









def EndpointReport(server,user,Pass):
    # FTP Mode
    sftp_mode = True
    ask = True
    while ask:
        sftp = input('Would you like to use SFTP or FTP to transfer reports? [SFTP/ftp]: ').lower()
        if sftp in (['sftp','sft','sf','s','']):
            print('!\nINFO: SFTP Mode will print "EOFError" during client connections; Disregard\n!\n!')
            ask = False
            None
        elif sftp in (['ftp','ft','f']):
            ask = False
            sftp_mode = False

    Date = datetime.now().strftime('%Y-%m-%d_%H%M')

    # ISE PAN Dictionary
    build_dict = True
    while build_dict:
        PAN_Dict = {}
        PAN_Dict.update({1:{'server':server,'user':user,'Pass':Pass}})
        count = 1
        ask = True
        while ask:
            Add = input('Would you like to add additional ISE PANs? [y/N]: ').lower()
            print('\n')
            if Add in (['yes','ye','y']):
                count += 1
                # Request ISE server FQDN
                serverA = input('Please Enter ISE fqdn: ').lower().strip()

                # Validate FQDN
                if serverA[-1] == '/':
                    serverA = serverA[:-1]
                if '//' in serverA:
                    serverA = serverA.split('//')[-1]

                # Perform Test Connection To FQDN
                s = socket.socket()
                print(f'Attempting to connect to {serverA} on port 22')
                try:
                    s.connect((serverA, 22))
                    print(f'Connecton successful to {serverA} on port 22\n')
                    s.close()
                    PAN_Dict.update({count:{'server':serverA,'user':user,'Pass':Pass}})
                    User = input('Do you need to add a different username and password for this PAN? [y/N]: ').lower()
                    if User in (['yes','ye','y']):
                        userA = input('Please Enter ISE CLI Username: ').lower().strip()
                        PassA = define_password()
                        PAN_Dict[count]['user'] = userA
                        PAN_Dict[count]['Pass'] = PassA
                except Exception:
                    print(f'Connection to {serverA} on port 22 failed:  {traceback.format_exc()}\n\n')
            else:
                ask = False
        ask = True
        while ask:
            rebuild = input('Do you need to re-enter additional PAN details? [y/N]: ').lower()
            print('\n')
            if rebuild in (['no','n','']):
                ask = False
                build_dict = False
            elif rebuild in (['yes','ye','y']):
                ask = False



    # Define Threading Queues
    NUM_THREADS = 20
    serverList = queue.Queue()
    outputList = queue.Queue()

    if len(PAN_Dict) < NUM_THREADS:
        NUM_THREADS = len(PAN_Dict)
    for key,value in PAN_Dict.items():
        serverList.put(value)

    # Random Generated Output
    outputDirectory = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])
    outputDirectory = f'{os.getcwd()}/{outputDirectory}/'
    if not os.path.exists(outputDirectory):
        os.makedirs(outputDirectory)
    # Create Dir for each ISE Node
    for key,value in PAN_Dict.items():
        PAN_DIR = f'{outputDirectory}{value["server"]}'
        if not os.path.exists(PAN_DIR):
            os.makedirs(PAN_DIR)

    outputFileName = f'{outputDirectory}EndpointReportLogs_{Date}.txt'

    # Start FTP Service
    try:
        if sftp_mode:
            SFTP = sftp_server(outputDirectory)
            SFTP.start()
            FTP_USER = SFTP.User
            FTP_PASS = SFTP.Pass
            FTP_ADDR = SFTP.Addr
            FTP_PORT = 22
        else:
            FTP = ftp_server(outputDirectory)
            FTP.start()
            FTP_USER = FTP.User
            FTP_PASS = FTP.Pass
            FTP_ADDR = FTP.Addr
            FTP_PORT = FTP.Port
    except:
        print(f'Failed to start SFTP/FTP service:  {traceback.format_exc()}\n\n')
        return

    # loop for devices
    for i in range(NUM_THREADS):
        Thread(target=COMMANDS, args=(PAN_Dict,serverList,outputList,sftp_mode,FTP_ADDR,FTP_USER,FTP_PASS,FTP_PORT)).start()
        time.sleep(1)

    with open(outputFileName,'w') as outputFile:
        numDone = 0
        while numDone < NUM_THREADS:
            result = outputList.get()
            if result is None:
                numDone += 1
            else:
                outputFile.write(result)

    # Stop FTP Service
    if sftp_mode:
        SFTP.stop()
    else:
        FTP.stop()
    return













#
#
#
# Run Script if main
if __name__ == '__main__':
    #
    #
    #
    # Initial input request
    print ('''
***********************************************************************************************
*                                                                                             *
*                   Cisco ISE CLI Tools (Written for Python 3.6+)                             *
*                                                                                             *
***********************************************************************************************
''')

    Test = False
    while not Test:
        # Request ISE server FQDN
        server = input('Please Enter ISE fqdn: ').lower().strip()

        # Validate FQDN
        if server[-1] == '/':
            server = server[:-1]
        if '//' in server:
            server = server.split('//')[-1]

        # Perform Test Connection To FQDN
        s = socket.socket()
        print(f'Attempting to connect to {server} on port 22')
        try:
            s.connect((server, 22))
            print(f'Connecton successful to {server} on port 22\n')
            Test = True
            s.close()
        except Exception:
            print(f'Connection to {server} on port 22 failed:  {traceback.format_exc()}\n\n')
            sys.exit()
    # Request User/Pass
    user = input('Please Enter ISE CLI Username: ').lower().strip()
    Pass = define_password()

    print ('''
***********************************************************************************************
*                                                                                             *
* TOOLS AVAILABLE:                                                                            *
*                                                                                             *
*  1. Download Endpoint Report                                                                *
*                                                                                             *
*  2. Password change for all ISE nodes                                                       *
*                                                                                             *
***********************************************************************************************
''')

    #
    #
    #
    # Run script until user cancels
    while True:
        Script = False
        while not Script:
            script = input('Please Select Script: ')
            if script == '1':
                Script = True
                EndpointReport(server,user,Pass)
            elif script == '2':
                Script = True
                PolicyDownload(config)
            elif script == '3':
                Script = True
                PolicyReport(config)
            else:
                print('INVALID ENTRY... ')

        # Ask to end the loop
        print ('''
***********************************************************************************************
*                                                                                             *
* TOOLS AVAILABLE:                                                                            *
*                                                                                             *
*  1. Download Endpoint Report                                                                *
*                                                                                             *
*  2. Password change for all ISE nodes                                                       *
*                                                                                             *
***********************************************************************************************
''')
        Loop = input('*\n*\nWould You Like To use another tool? [y/N]: ').lower()
        if Loop not in (['yes','ye','y','1','2','3','4']):
            break







