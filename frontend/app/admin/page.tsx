"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminService } from "@/services/adminService";
import { ApiError } from "@/services/apiClient";
import type { UserPublic } from "@/types/auth";
import { ROLE_LABEL } from "@/lib/role-labels";

/** ADM-00 사용자·권한 관리: GET /admin/users 실데이터. */
export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserPublic[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    adminService
      .listUsers()
      .then((data) => setUsers(data.items))
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "사용자 목록을 불러오지 못했습니다."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>사용자·권한 관리</CardTitle>
      </CardHeader>
      <CardContent>
        {errorMessage ? (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="text-sm text-destructive">{errorMessage}</p>
            <Button
              variant="outline"
              onClick={() => {
                setUsers(null);
                setErrorMessage(null);
                load();
              }}
            >
              다시 시도
            </Button>
          </div>
        ) : users === null ? (
          <Skeleton className="h-32 w-full" />
        ) : users.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">등록된 사용자가 없습니다.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>이름</TableHead>
                <TableHead>이메일</TableHead>
                <TableHead>역할</TableHead>
                <TableHead>가입일</TableHead>
                <TableHead>최근 로그인</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.user_id}>
                  <TableCell className="font-medium">{user.display_name}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{user.email}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{ROLE_LABEL[user.role] ?? user.role}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {user.created_at ? user.created_at.slice(0, 10) : "-"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {user.last_login_at ? user.last_login_at.slice(0, 16).replace("T", " ") : "-"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
