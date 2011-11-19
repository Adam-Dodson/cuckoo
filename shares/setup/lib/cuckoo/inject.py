#!/usr/bin/python
# Cuckoo Sandbox - Automated Malware Analysis
# Copyright (C) 2010-2011  Claudio "nex" Guarnieri (nex@cuckoobox.org)
# http://www.cuckoobox.org
#
# This file is part of Cuckoo.
#
# Cuckoo is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Cuckoo is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses/.

import os
import sys
from ctypes import sizeof, byref, c_int, c_ulong, wintypes
import ctypes

sys.path.append("\\\\VBOXSVR\\setup\\lib\\")

from cuckoo.defines import *
from cuckoo.logging import *

# The following function was taken from PyBox:
# http://code.google.com/p/pyboxed
########################################################################
# Copyright (c) 2010
# Felix S. Leder <leder<at>cs<dot>uni-bonn<dot>de>
# Daniel Plohmann <plohmann<at>cs<dot>uni-bonn<dot>de>
# All rights reserved.
########################################################################
def grant_debug_privilege(pid = 0):
    """ grant SeDebugPrivilege to own process
    @param pid: Process id to set permissions of (or 0 if current)
    @type pid: int
    @return: True if operation was successful, 
              False otherwise
    """
    ADVAPI32.OpenProcessToken.argtypes = (wintypes.HANDLE,
                                          wintypes.DWORD,
                                          ctypes.POINTER(wintypes.HANDLE))

    ADVAPI32.LookupPrivilegeValueW.argtypes = (wintypes.LPWSTR,
                                               wintypes.LPWSTR,
                                               ctypes.POINTER(LUID))
    ADVAPI32.AdjustTokenPrivileges.argtypes = (wintypes.HANDLE,
                                               wintypes.BOOL,
                                               ctypes.POINTER(TOKEN_PRIVILEGES),
                                               wintypes.DWORD,
                                               ctypes.POINTER(TOKEN_PRIVILEGES),
                                               ctypes.POINTER(wintypes.DWORD))

    h_process = None
    if pid == 0:
        h_process = KERNEL32.GetCurrentProcess()
    else:
        h_process = KERNEL32.OpenProcess(PROCESS_ALL_ACCESS,
                                         False,
                                         pid)

    if not h_process:
        return False    

    # obtain token to process
    h_current_token = wintypes.HANDLE() 
    if not ADVAPI32.OpenProcessToken(h_process,
                                     TOKEN_ALL_ACCESS,
                                     h_current_token): 
        return False
    
    # look up current privilege value
    se_original_luid = LUID()
    if not ADVAPI32.LookupPrivilegeValueW(None,
                                          "SeDebugPrivilege",
                                          se_original_luid):
        return False

    luid_attributes = LUID_AND_ATTRIBUTES()
    luid_attributes.Luid = se_original_luid
    luid_attributes.Attributes = SE_PRIVILEGE_ENABLED
    token_privs = TOKEN_PRIVILEGES()
    token_privs.PrivilegeCount = 1;
    token_privs.Privileges = luid_attributes; 
    
    if not ADVAPI32.AdjustTokenPrivileges(h_current_token,
                                          False,
                                          token_privs,
                                          0,
                                          None,
                                          None):
        return False
    
    KERNEL32.CloseHandle(h_current_token)
    KERNEL32.CloseHandle(h_process)
    
    return True

def cuckoo_inject(pid, dll_path):
    if not os.path.exists(dll_path):
        return False

    # If target process is current, abort.
    if pid == os.getpid():
        return False

    if not grant_debug_privilege():
        log("Unable to grant debug privileges on Cuckoo process (GLE=%s)."
            % KERNEL32.GetLastError(), "ERROR")
    else:
        log("Successfully granted debug privileges on Cuckoo process.")

    h_process = KERNEL32.OpenProcess(PROCESS_ALL_ACCESS, False, int(pid))

    if not h_process:
        return False

    ll_param = KERNEL32.VirtualAllocEx(h_process,
                                       0,
                                       len(dll_path),
                                       MEM_RESERVE | MEM_COMMIT,
                                       PAGE_READWRITE)

    bytes_written = c_int(0)

    if not KERNEL32.WriteProcessMemory(h_process,
                                       ll_param,
                                       dll_path,
                                       len(dll_path),
                                       byref(bytes_written)):
        return False

    lib_addr = KERNEL32.GetProcAddress(
                    KERNEL32.GetModuleHandleA("kernel32.dll"),
                    "LoadLibraryA")

    new_thread_id = c_ulong(0)

    if not KERNEL32.CreateRemoteThread(h_process,
                                       None,
                                       0,
                                       lib_addr,
                                       ll_param,
                                       0,
                                       byref(new_thread_id)):
        return False

    return True
