#
# Copyright 2015 Naver Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import subprocess
import util
import unittest
import testbase
import default_cluster
import os
import smr_mgmt
import redis_mgmt
import time
import load_generator
import config
import copy

class TestScaleout(unittest.TestCase):
    cluster = config.clusters[0]
    max_load_generator = 10
    load_gen_thrd_list = {}

    @classmethod
    def setUpClass( cls ):
        return 0

    @classmethod
    def tearDownClass( cls ):
        return 0

    def setUp(self):
        util.set_process_logfile_prefix( 'TestScaleout_%s' % self._testMethodName )
        conf = {'smr_log_delete_delay':60}
        self.conf_checker = default_cluster.initialize_starting_up_smr_before_redis( self.cluster, conf=conf )
        self.assertIsNotNone(self.conf_checker, 'failed to initialize cluster')

    def tearDown(self):
        testbase.defaultTearDown(self)

    def test_scaleout(self):
        util.print_frame()

        # start load generator
        util.log("start load_generator")
        for i in range(self.max_load_generator):
            ip, port = util.get_rand_gateway(self.cluster)
            self.load_gen_thrd_list[i] = load_generator.LoadGenerator(i, ip, port, ops_limit=500)
            self.load_gen_thrd_list[i].start()

        time.sleep(5) # generate load for 5 sec
        util.log("started load_generator")

        # servers for scale out
        servers = [config.server4, config.server5, config.server6]
        leader_cm = self.cluster['servers'][0]

        # start migration
        migration_count = 5
        for i in range(migration_count):
            # Scale out
            cluster = config.clusters[0]
            ret = util.install_pg(cluster, servers, leader_cm)
            self.assertEqual(True, ret, 'Scale out fail. util.install_pg(returns false')

            time.sleep(5)
            # pg0 -> pg1
            cluster = config.clusters[1]
            ret = util.migration(cluster, 0, 1, 4096, 8191, 40000)
            self.assertEqual(True, ret, 'Migration Fail 0 -> 1')

            # pg0 <- pg1
            cluster = config.clusters[1]
            ret = util.migration(cluster, 1, 0, 4096, 8191, 40000)
            self.assertEqual(True, ret, 'Migration Fail 1 <- 0')

            # Scale in

            #TODO Temporary
            #cluster = config.clusters[0]
            #for server in cluster['servers']:
            #    if testbase.request_to_shutdown_hbc(server) is not 0:
            #        util.log('scale in : failed to request to shutdown hbc')
            #        self.assertFalse('scale in : failed to request to shutdown hbc')
            #time.sleep(5)
            ###############

            cluster = config.clusters[1]
            ret = util.uninstall_pg(cluster, servers, leader_cm)
            self.assertEqual(True, ret, 'Scale in fail. util.uninstall_pg(returns false')

            #TODO Temporary
            #cluster = config.clusters[0]
            #for server in cluster['servers']:
            #    if testbase.request_to_start_heartbeat_checker( server ) is not 0:
            #        util.log('scale in : failed to start hbc')
            #        self.assertFalse('scale in : failed to start hbc')
            #time.sleep(5)
            ###############

            # check consistency
            ok = True
            for j in range(len(self.load_gen_thrd_list)):
                if self.load_gen_thrd_list[j].isConsistent() == False:
                    ok = False
                    break
            if not ok:
                break;

        time.sleep(5) # generate load for 5 sec
        # check consistency of load_generator
        for i in range(len(self.load_gen_thrd_list)):
            self.load_gen_thrd_list[i].quit()
        for i in range(len(self.load_gen_thrd_list)):
            self.load_gen_thrd_list[i].join()
            self.assertTrue(self.load_gen_thrd_list[i].isConsistent(), 'Inconsistent after migration')

    def test_delete_smrlog_after_scaleout(self):
        util.print_frame()

        # start load generator
        util.log("start load_generator")
        for i in range(self.max_load_generator):
            ip, port = util.get_rand_gateway(self.cluster)
            self.load_gen_thrd_list[i] = load_generator.LoadGenerator(i, ip, port, ops_limit=500)
            self.load_gen_thrd_list[i].start()

        time.sleep(5) # generate load for 5 sec
        util.log("started load_generator")

        # servers for scale out
        servers = [config.server4, config.server5, config.server6]
        leader_cm = self.cluster['servers'][0]

        # Scale out
        cluster = config.clusters[0]
        ret = util.install_pg(cluster, servers, leader_cm)
        self.assertEqual(True, ret, 'Scale out fail. util.install_pg(returns false')

        time.sleep(5)
        # pg0 -> pg1
        cluster = config.clusters[1]
        ret = util.migration(cluster, 0, 1, 8000, 8191, 40000)
        self.assertEqual(True, ret, 'Migration Fail 0 -> 1')

        # get log file
        old_logs = {}
        for s in config.clusters[0]['servers']:
            parent_dir, log_dir = util.smr_log_dir(s['id'])
            path = '%s/%s' % (parent_dir, log_dir)
            old_logs[s['id']] = util.ls(path)

        # bgsave in order to make smrlogs deleted.
        for s in config.clusters[0]['servers']:
            bgsave_ret = util.bgsave(s)
            self.assertTrue(bgsave_ret, 'failed to bgsave. pgs%d' % s['id'])
            util.log('bgsave pgs%d is done.')

        # check consistency
        ok = True
        for j in range(len(self.load_gen_thrd_list)):
            self.assertTrue(self.load_gen_thrd_list[j].isConsistent(),
                    'Inconsistent after migration')

        # is smr-replicator delete smrlogs?
        i = 0
        while i < 20:
            i += 1
            # get current log files
            cur_logs = {}
            for s in config.clusters[0]['servers']:
                parent_dir, log_dir = util.smr_log_dir(s['id'])
                path = '%s/%s' % (parent_dir, log_dir)
                cur_logs[s['id']] = util.ls(path)

            # compare old and new
            temp_old_logs = copy.deepcopy(old_logs)
            for id, nl in cur_logs.items():
                ol = temp_old_logs.get(id)
                self.assertNotEqual(ol, None, "failed to check logfiles. old logs for smr-replicator '%d' is not exist." % id)

                for log in nl:
                    if log in ol:
                        ol.remove(log)

            ok = True
            for id, ol in temp_old_logs.items():
                if len(ol) == 0:
                    ok = False

            util.log('Loop %d ---------------------------------------------------------' % i)
            util.log('deleted smrlog files: %s' % util.json_to_str(temp_old_logs))

            if ok:
                break

            time.sleep(10)

        self.assertTrue(ok, 'smr-replicator does not delete smrlogs.')
        util.log('smr-replicator deletes smrlogs.')

        # check consistency of load_generator
        for i in range(len(self.load_gen_thrd_list)):
            self.load_gen_thrd_list[i].quit()
        for i in range(len(self.load_gen_thrd_list)):
            self.load_gen_thrd_list[i].join()
            self.assertTrue(self.load_gen_thrd_list[i].isConsistent(), 'Inconsistent after migration')

        # Go back to initial configuration
        # Rollback migration
        self.assertTrue(util.migration(cluster, 1, 0, 8000, 8191, 40000),
                'failed to rollback migration')

        # Cleanup pgs
        self.assertTrue(util.uninstall_pg(cluster, servers, leader_cm),
                'failed to cleanup pgs')
