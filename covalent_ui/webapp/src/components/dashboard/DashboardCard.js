/**
 * This file is part of Covalent.
 *
 * Licensed under the Apache License 2.0 (the "License"). A copy of the
 * License may be obtained with this software package or at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Use of this file is prohibited except in compliance with the License.
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import React, { useEffect, useState } from 'react'
import {
  Paper,
  Typography,
  Divider,
  Skeleton,
  Snackbar,
  SvgIcon,
} from '@mui/material'
import { Box } from '@mui/system'
import { statusLabel, secondsToHms } from '../../utils/misc'
import { useDispatch, useSelector } from 'react-redux'
import { fetchDashboardOverview } from '../../redux/dashboardSlice'
import { ReactComponent as closeIcon } from '../../assets/close.svg'

const DashboardCard = () => {
  const dispatch = useDispatch()
  // check if socket message is received and call API
  const callSocketApi = useSelector((state) => state.common.callSocketApi)
  // selecting the dashboardOverview from redux state
  const dashboardStats = useSelector(
    (state) => state.dashboard.dashboardOverview
  )
  const isError = useSelector(
    (state) => state.dashboard.fetchDashboardOverview.error
  )
  //check if any dispatches are deleted and call the API
  const isDeleted = useSelector((state) => state.dashboard.dispatchesDeleted)

  const [openSnackbar, setOpenSnackbar] = useState(Boolean(isError))

  const fetchDashboardOverviewResult = () => {
    dispatch(fetchDashboardOverview())
  }

  useEffect(() => {
    fetchDashboardOverviewResult()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDeleted, callSocketApi])

  useEffect(() => {
    if (isError) setOpenSnackbar(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isError])

  return (
    <Paper
      data-testid="dashboardCard"
      elevation={0}
      sx={{
        p: 3,
        mb: 2,
        borderRadius: '8px',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Typography fontSize="h5.fontSize" sx={{ color: '#FFFFFF' }}>
          Dispatch list
        </Typography>
        <Snackbar
          open={openSnackbar}
          autoHideDuration={3000}
          message="Something went wrong,please contact the administrator!"
          onClose={() => setOpenSnackbar(false)}
          action={
            <SvgIcon
              data-testid="closeIcon"
              sx={{
                mt: 2,
                zIndex: 2,
                cursor: 'pointer',
              }}
              component={closeIcon}
              onClick={() => setOpenSnackbar(false)}
            />
          }
        />
      </Box>
      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'space-around' }}>
        <DashBoardCardItems
          content={dashboardStats.total_jobs_running}
          desc="Total jobs running"
          align="center"
          isSkeletonPresent={!dashboardStats}
        />
        <DashboardDivider />
        <DashBoardCardItems
          content={dashboardStats.total_jobs_completed}
          desc="Total jobs done"
          align="center"
          isSkeletonPresent={!dashboardStats}
        />
        <DashboardDivider />
        <DashBoardCardItems
          content={
            statusLabel(dashboardStats.latest_running_task_status) || 'N/A'
          }
          desc="Latest running task status"
          align="center"
          isSkeletonPresent={!dashboardStats}
        />
        <DashboardDivider />
        <DashBoardCardItems
          content={
            dashboardStats?.total_dispatcher_duration
              ? secondsToHms(dashboardStats.total_dispatcher_duration)
              : 'N/A'
          }
          desc="Total dispatcher duration"
          align="flex-end"
          isSkeletonPresent={!dashboardStats}
        />
      </Box>
    </Paper>
  )
}

export const DashBoardCardItems = ({
  desc,
  content,
  align,
  isSkeletonPresent,
}) => (
  <Box
    sx={{
      display: 'flex',
      mr: 1,
      flexDirection: 'column',
      alignItems: align,
      width: '100%',
    }}
  >
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
      }}
    >
      <Typography fontSize="h5.fontSize" color="text.secondary">
        {isSkeletonPresent ? (
          <Skeleton data-testid="skeleton" width={25} />
        ) : content || content === 0 ? (
          content
        ) : (
          'N/A'
        )}
      </Typography>
      <Typography sx={{ marginTop: '16px' }} color="text.primary">
        {' '}
        {desc}
      </Typography>
    </Box>
  </Box>
)

const DashboardDivider = () => (
  <Divider
    flexItem
    orientation="vertical"
    sx={(theme) => ({
      borderColor: theme.palette.background.coveBlack02,
      ml: 1,
    })}
  />
)

export default DashboardCard
