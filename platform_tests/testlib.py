import subprocess as sp
import os
import shutil
import tempfile
import pwd
import time

_NORMUSER = 'normuser'
_RUNNER_LOG_FILE_FOR_ROOT = '/root/.jobber-log'
_RUNNER_LOG_FILE_FOR_NORMUSER = '/home/{0}/.jobber-log'.\
    format(_NORMUSER) 

def sp_check_output(args):
    proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE)
    out, err = proc.communicate()
    if proc.returncode != 0:
        msg = "{args} failed.\nStdout:\n{out}\nStderr:\n{err}".format(
                args=args,
                out=out,
                err=err
            )
        raise AssertionError(msg)
    if len(err) > 0:
        print("STDERR: {0}".format(err))
    return out

def _find_file(name, dir):
    for dirpath, dirnames, filenames in os.walk(dir):
        if name in filenames:
            return os.path.join(dirpath, name)
    return None

def find_program(name):
    dirs = ['/bin', '/sbin', '/usr']
    for dir in dirs:
        path = _find_file(name, dir)
        if path is not None:
            return path
    raise Exception("Cannot find program {0}".format(name))
    
def using_systemd():
    try:
        find_program('systemctl')
    except:
        return False
    else:
        return True

def get_jobbermaster_logs():
    if using_systemd():
        return sp_check_output(['journalctl', '-u', 'jobber'])
    else:
        args = ['tail', '-n', '20', '/var/log/messages']
        lines = sp_check_output(args).split('\n')
        lines = [l for l in lines if 'jobbermaster' in l]
        return '/n'.join(lines)

class testlib(object):
    ROBOT_LIBRARY_VERSION = 1.0

    def __init__(self):
        # get paths to stuff
        self._root_jobfile_path = '/root/.jobber'
        self._normuser_jobfile_path = '/home/' + _NORMUSER + '/.jobber'
        self._jobber_path = find_program('jobber')
        self._tmpfile_dir = '/JobberTestTmp'

    def make_tempfile_dir(self):
        # make temp-file dir
        os.mkdir(self._tmpfile_dir)
        os.chmod(self._tmpfile_dir, 0777)

    def rm_tempfile_dir(self):
        shutil.rmtree(self._tmpfile_dir)
    
    def make_tempfile(self):
        fd, path = tempfile.mkstemp(dir=self._tmpfile_dir)
        os.close(fd)
        os.chmod(path, 0666)
        return path
    
    def restart_service(self):
        # restart jobber service
        try:
            if using_systemd():
                sp_check_output(['systemctl', 'restart', 'jobber'])
            else:
                sp_check_output(['service', 'jobber', 'restart'])
        except Exception as e:
            self.print_debug_info()
            raise e
            
        # wait for it to be ready
        started = False
        stop_time = time.time() + 10
        while time.time() < stop_time and not started:
            args = [self._jobber_path, 'list']
            proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE)
            _, err = proc.communicate()
            if proc.returncode == 0:
                started = True
            else:
                time.sleep(1)
        if not started:
            msg = "Failed to start jobber service!"
            msg += " ('jobber list' returned '{0}')".\
                format(err.strip())
            raise AssertionError(msg)
    
    def print_debug_info(self):
        log = ''
    
        # get service status
        log += "Jobber service status:\n"
        if using_systemd():
            args = ['systemctl', 'status', 'jobber']
        else:
            args = ['service', 'jobber', 'status']
        try:
            log += sp_check_output(args)
        except Exception as e:
            log += "[{0}]".format(e)
            
        # get syslog msgs
        log += "\n\njobbermaster logs:\n"
        try:
            log += get_jobbermaster_logs()
        except Exception as e:
            log += "[{0}]".format(e)
        
        # get jobberrunner logs
        log_files = [
            _RUNNER_LOG_FILE_FOR_ROOT, 
            _RUNNER_LOG_FILE_FOR_NORMUSER,
        ]
        for lf in log_files:
            log += "\n\n{0}:\n".format(lf)
            try:
                with open(lf) as f:
                    log += f.read()
            except Exception as e:
                log += "[{0}]".format(e)
        
        print(log)
    
    def make_jobfile(self, job_name, cmd, time="*", notify_prog=None):
        jobs_sect = """[jobs]
- name: {job_name}
  cmd: {cmd}
  time: '{time}'
  notifyOnError: true
""".format(job_name=job_name, cmd=cmd, time=time)
        if notify_prog is None:
            return jobs_sect
        else:
            prefs_sect = """[prefs]
notifyProgram: {notify_prog}

""".format(notify_prog=notify_prog)
            return prefs_sect + jobs_sect

    def install_root_jobfile(self, contents):
        '''
        :return: Number of jobs loaded.
        '''
        
        # make jobfile
        with open(self._root_jobfile_path, 'w') as f:
            f.write(contents)

        # reload it
        output = sp_check_output([self._jobber_path, 'reload'])
        return int(output.split()[1])

    def install_normuser_jobfile(self, contents):
        '''
        :return: Number of jobs loaded.
        '''
        
        # make jobfile
        print("Installing jobfile at {path}".\
              format(path=self._normuser_jobfile_path))
        pwnam = pwd.getpwnam(_NORMUSER)
        os.setegid(pwnam.pw_gid)
        os.seteuid(pwnam.pw_uid)
        with open(self._normuser_jobfile_path, 'w') as f:
            f.write(contents)
        os.seteuid(0)
        os.setegid(0)

        # reload it
        output = sp_check_output(['sudo', '-u', _NORMUSER, \
                                  self._jobber_path, 'reload'])
        return int(output.split()[1])

    def rm_jobfiles(self):
        # rm jobfile
        if os.path.exists(self._root_jobfile_path):
            os.unlink(self._root_jobfile_path)
        if os.path.exists(self._normuser_jobfile_path):
            os.unlink(self._normuser_jobfile_path)
    
    def jobber_log(self):
        return sp_check_output([self._jobber_path, 'log'])
    
    def pause_job(self, job):
        sp_check_output([self._jobber_path, 'pause', job])
    
    def resume_job(self, job):
        sp_check_output([self._jobber_path, 'resume', job])
    
    def test_job(self, job):
        sp_check_output([self._jobber_path, 'test', job])
    
    def chmod(self, path, mode):
        os.chmod(path, int(mode, base=8))
        stat = os.stat(path)
        print("Mode of {path} is now {mode}".\
              format(path=path, mode=oct(stat.st_mode & 0777)))
    
    def chown(self, path, user):
        pwnam = pwd.getpwnam(user)
        os.chown(path, pwnam.pw_uid, pwnam.pw_gid)

    def runner_proc_info(self):
        args = ['ps', '-C', 'jobberrunner', '-o', 'uid,tty']
        output = sp_check_output(args)
        records = [line for line in output.split('\n')[1:] \
                   if len(line.strip()) > 0]
        records.sort()
        return '\n'.join(records)
    
    def nbr_of_runner_procs_should_be_same(self, orig_proc_info):
        new_proc_info = self.runner_proc_info()
        if orig_proc_info != new_proc_info:
            print("Original runner procs:\n{0}".format(orig_proc_info))
            print("New runner procs:\n{0}".format(new_proc_info))
            raise AssertionError("Number of runner procs has changed!")
    
    def runner_procs_should_not_have_tty(self):
        # This is to avoid a particular vulnerability
        # (http://www.halfdog.net/Security/2012/TtyPushbackPrivilegeEscalation/)
        proc_info = self.runner_proc_info()
        for line in proc_info.split('\n'):
            try:
                tty = line.split()[1]
            except IndexError as _:
                print("Error: " + line)
                raise
            if tty != '?':
                print("Runner procs:\n{0}".format(proc_info))
                raise AssertionError("A runner proc has a controlling tty")
    
    def _check_jobber_list_output(self, output, exp_job_names):
        lines = output.split("\n")
        if len(lines) <= 1:
            msg = "Expected output to have multiple lines: \"{0}\"".\
                format(output)
            raise AssertionError(msg)
        listed_jobs = set([line.split()[0] for line in lines[1:]])
        exp_job_names = set(exp_job_names.split(","))
        if listed_jobs != exp_job_names:
            msg = "Expected listed jobs to be {exp}, but was {act}".\
                format(exp=exp_job_names, act=listed_jobs)
            raise AssertionError(msg)
    
    def jobber_list_as_root_should_return(self, job_names, \
                                          all_users=False):
        # do 'jobber list'
        all_users = bool(all_users)
        args = [self._jobber_path, 'list']
        if all_users:
            args.append('-a')
        print("Cmd: {0}".format(args))
        output = sp_check_output(args).strip()
        print(output)
        
        # check output
        self._check_jobber_list_output(output, job_names)
    
    def jobber_list_as_normuser_should_return(self, job_names, \
                                              all_users=False):
        # do 'jobber list'
        output = sp_check_output(['sudo', '-u', _NORMUSER, \
                                  self._jobber_path, 'list']).strip()
        print(output)
        
        # check output
        self._check_jobber_list_output(output, job_names)
    
    def nbr_of_lines_in_string_should_be(self, string, nbr, msg=None):
        lines = string.split("\n")
        if len(lines) != int(nbr):
            base_msg = ("Number of lines in string should be {nbr}, " \
                   "but was {actual}").format(nbr=nbr, 
                                              actual=len(lines))
            if msg is None:
                raise AssertionError(base_msg)
            else:
                raise AssertionError("{msg}: {base_msg}".\
                                    format(msg=msg, base_msg=base_msg))
    
    def jobbermaster_has_not_crashed(self):
        try:
            logs = get_jobbermaster_logs()
        except:
            pass
        else:
            if "panic" in logs:
                print(logs)
                raise AssertionError("jobbermaster crashed")
    
    def jobberrunner_for_root_has_not_crashed(self):
        try:
            with open(_RUNNER_LOG_FILE_FOR_ROOT) as f:
                logs = f.read()
        except:
            pass
        else:
            if "panic" in logs:
                print(logs)
                raise AssertionError("jobberrunner for root crashed")
    
    def jobberrunner_for_normuser_has_not_crashed(self):
        try:
            with open(_RUNNER_LOG_FILE_FOR_NORMUSER) as f:
                logs = f.read()
        except:
            pass
        else:
            if "panic" in logs:
                print(logs)
                raise AssertionError("jobberrunner for normuser crashed")