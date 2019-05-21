import subprocess
import argparse
import sys
# ok
def cmd(cmd_str, begin, end):
    printing=False
    shellEnd=0
    cmd = subprocess.Popen(cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(cmd.stdout.readline, ''):
        line = line.decode('utf-8').replace('\r', '').replace('\n', '')
        if end in line and printing==True:
            break
        if begin in line:
            printing=True
        if printing==True and line!='':
            print(line)
        sys.stdout.flush()
        if line=='':
            shellEnd=shellEnd+1
            if shellEnd>5:
              break
        else:
            shellEnd=0

if __name__ == '__main__':
    ## ARGUMENT PARSER
    parser = argparse.ArgumentParser(description='Run SHELL-CMD and only print between BEGIN and END')
    parser.add_argument('cmd', type=str,help='xml-filepath')
    parser.add_argument('b', help='String at Beginning')
    parser.add_argument('e', help='String at End')
    args = parser.parse_args()

    cmd(args.cmd,args.b,args.e)
