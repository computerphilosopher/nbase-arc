/*
 * Copyright 2015 Naver Corp.
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *     http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.navercorp.nbasearc.confmaster.context;

import com.navercorp.nbasearc.confmaster.ConfMasterException.MgmtDuplicatedReservedCallException;

public class ReservedCallHolder {
    
    private ReservedCall call = null;

    public boolean hasNextCall() {
        return call != null;
    }

    public ReservedCall pollCall() {
        try {
            return call;
        } finally {
            call = null;
        }
    }
    
    public void setCall(ReservedCall call) throws MgmtDuplicatedReservedCallException {
        if (this.call != null) {
            throw new MgmtDuplicatedReservedCallException(
                    "Workflow to run on next time is already set. Workfolw="
                            + this.call);
        }
        this.call = call;
    }
    
}
